import { AppShell } from "@/components/app-shell"
import { AppProviders } from "@/components/providers"

/** Authenticated shell for chat and other non-URL-specific SPA views. */
export default function ChatRoute() {
  return (
    <AppProviders>
      <AppShell />
    </AppProviders>
  )
}
