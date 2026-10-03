"use client";

import { useState } from "react";
import { Sidebar } from "@/components/shell/Sidebar";
import { TopBar } from "@/components/shell/TopBar";
import { StatusBar } from "@/components/shell/StatusBar";
import { DataModeBanner } from "@/components/shell/DataModeBanner";
import { CommandPalette } from "@/components/shell/CommandPalette";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [cmdOpen, setCmdOpen] = useState(false);
  // Default telemetry props (can be supplemented by React Query / SSE hooks)
  const [dataMode] = useState<string>("HISTORICAL");
  const [regime] = useState<string>("RISK_ON");
  const [regimeConfidence] = useState<number>(0.84);
  const [sseStatus] = useState<"connected" | "reconnecting" | "offline">("connected");

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[var(--bg-base)]">
      {/* Navigation Sidebar */}
      <Sidebar />

      {/* Main Workspace Frame */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Top Data Mode Banner for Synthetic / Replay */}
        <DataModeBanner dataMode={dataMode} />

        {/* Global Navigation TopBar */}
        <TopBar
          onOpenCommandPalette={() => setCmdOpen(true)}
          dataMode={dataMode}
          regime={regime}
          regimeConfidence={regimeConfidence}
          sseStatus={sseStatus}
        />

        {/* Dynamic Route View */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6 bg-[var(--bg-base)]">
          {children}
        </main>

        {/* Persistent Bottom Status Bar */}
        <StatusBar />

        {/* Global Command Palette */}
        <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
      </div>
    </div>
  );
}
