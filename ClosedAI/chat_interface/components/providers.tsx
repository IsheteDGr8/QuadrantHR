"use client"

import type React from "react"
import { useEffect } from "react"
import { ChatProvider } from "@/lib/chat-store"
import { SkillsProvider } from "@/lib/skills-store"
import { McpProvider } from "@/lib/mcp-store"
import { AgentRuntimeProvider } from "@/lib/agent-runtime"
import { NavigationProvider } from "@/lib/navigation"
import { ensureWorkHydrated } from "@/lib/work-store"
import { AuthGate } from "@/components/auth-gate"
import { Toaster } from "@/components/ui/sonner"

function WorkHydrate() {
  useEffect(() => {
    ensureWorkHydrated()
  }, [])
  return null
}

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <AgentRuntimeProvider>
      <ChatProvider>
        <SkillsProvider>
          <McpProvider>
            <NavigationProvider>
              <AuthGate>
                <WorkHydrate />
                {children}
                <Toaster theme="light" position="bottom-center" />
              </AuthGate>
            </NavigationProvider>
          </McpProvider>
        </SkillsProvider>
      </ChatProvider>
    </AgentRuntimeProvider>
  )
}
