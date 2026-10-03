"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export type SSEStatus = "connected" | "reconnecting" | "offline";

export interface EventStreamOptions<T> {
  url: string;
  enabled?: boolean;
  onMessage?: (data: T) => void;
  reconnectIntervalMs?: number;
  maxReconnectAttempts?: number;
}

export function useEventStream<T = any>({
  url,
  enabled = true,
  onMessage,
  reconnectIntervalMs = 2000,
  maxReconnectAttempts = 5,
}: EventStreamOptions<T>) {
  const [status, setStatus] = useState<SSEStatus>("offline");
  const [lastData, setLastData] = useState<T | null>(null);
  const [isPaused, setIsPaused] = useState(false);
  const [errorCount, setErrorCount] = useState(0);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastEventIdRef = useRef<string | null>(null);

  const connect = useCallback(() => {
    if (!enabled || isPaused || typeof window === "undefined") {
      return;
    }

    // Build URL with Last-Event-ID if available
    let streamUrl = url;
    if (lastEventIdRef.current) {
      const separator = streamUrl.includes("?") ? "&" : "?";
      streamUrl = `${streamUrl}${separator}last_event_id=${encodeURIComponent(lastEventIdRef.current)}`;
    }

    try {
      const es = new EventSource(streamUrl);
      eventSourceRef.current = es;

      es.onopen = () => {
        setStatus("connected");
        setErrorCount(0);
      };

      es.onmessage = (event) => {
        if (event.lastEventId) {
          lastEventIdRef.current = event.lastEventId;
        }

        try {
          const parsed = JSON.parse(event.data) as T;
          setLastData(parsed);
          if (onMessage) {
            onMessage(parsed);
          }
        } catch {
          // Heartbeat or plain text comment
        }
      };

      es.onerror = () => {
        es.close();
        eventSourceRef.current = null;
        setStatus("reconnecting");
        setErrorCount((prev) => prev + 1);

        // Schedule reconnect with backoff & jitter
        const backoff = Math.min(reconnectIntervalMs * 1.5 ** errorCount, 15000);
        const jitter = Math.random() * 1000;
        reconnectTimeoutRef.current = setTimeout(() => {
          if (!isPaused && enabled) {
            connect();
          }
        }, backoff + jitter);
      };
    } catch {
      setStatus("offline");
    }
  }, [url, enabled, isPaused, errorCount, reconnectIntervalMs, onMessage]);

  // Tab visibility management: pause stream when tab hidden to save resources
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
          setStatus("offline");
        }
      } else if (document.visibilityState === "visible" && enabled && !isPaused) {
        connect();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [connect, enabled, isPaused]);

  // Main lifecycle
  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setStatus("offline");
    };
  }, [connect]);

  const togglePause = useCallback(() => {
    setIsPaused((prev) => {
      const next = !prev;
      if (next && eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
        setStatus("offline");
      }
      return next;
    });
  }, []);

  return {
    status,
    lastData,
    isPaused,
    togglePause,
  };
}
