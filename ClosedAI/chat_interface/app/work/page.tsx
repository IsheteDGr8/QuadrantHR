"use client"

import { AppShell } from "@/components/app-shell"
import { AppProviders } from "@/components/providers"

/** View is owned by NavigationProvider (URL + localStorage). Do not force "work"
 * here — that overwrote a restored chat whenever the address bar was still /work. */
export default function WorkRoute() {
  return (
    <AppProviders>
      <AppShell />
    </AppProviders>
  )
}
