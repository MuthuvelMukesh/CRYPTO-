import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

/**
 * CI Guard: Enforce Invariant 2 (No fabricated data & no hardcoded numeric display fallbacks).
 * Disallows patterns like: `?? 64000`, `|| 3400`, `?? 100`, etc.
 */
describe("CI Display Fallback Guard (Invariant 2)", () => {
  const srcDir = path.resolve(__dirname, "../src");

  function getFiles(dir: string): string[] {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    const files: string[] = [];
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        files.push(...getFiles(fullPath));
      } else if (entry.isFile() && (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx"))) {
        // Exclude schema.d.ts generated file
        if (!entry.name.includes("schema.d.ts")) {
          files.push(fullPath);
        }
      }
    }
    return files;
  }

  it("ensures no component contains hardcoded numeric fallback expressions", () => {
    const files = getFiles(srcDir);
    expect(files.length).toBeGreaterThan(0);

    const bannedPatterns = [
      /\?\?\s*64000/g,
      /\|\|\s*3400/g,
      /\?\?\s*50000/g,
      /\?\?\s*\d{4,}/g, // Fallback to large numeric constant
      /\?\?\s*["']\+?\d+\.?\d*\%["']/g, // Fallback to hardcoded percentage string e.g. "?? '+5.2%'"
    ];

    const violations: { file: string; line: number; match: string }[] = [];

    for (const file of files) {
      const content = fs.readFileSync(file, "utf-8");
      const lines = content.split("\n");

      lines.forEach((line, index) => {
        // Ignore comments or tests
        if (line.trim().startsWith("//") || line.trim().startsWith("/*")) return;

        for (const pattern of bannedPatterns) {
          const match = line.match(pattern);
          if (match) {
            violations.push({
              file: path.relative(srcDir, file),
              line: index + 1,
              match: match[0],
            });
          }
        }
      });
    }

    if (violations.length > 0) {
      console.error("Hardcoded numeric fallback violations found:", violations);
    }

    expect(violations).toEqual([]);
  });
});
