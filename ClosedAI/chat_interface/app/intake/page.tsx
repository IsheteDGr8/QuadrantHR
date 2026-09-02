"use client"

import { AppShell } from "@/components/app-shell"
import { AppProviders } from "@/components/providers"

export default function IntakeRoute() {
  return (
    <AppProviders>
      <AppShell />
    </AppProviders>
  )
}
