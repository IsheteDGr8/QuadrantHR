import {
  channelMeta,
  dispositionMeta,
  type IntakeCluster,
  type IntakeItem,
} from "@/lib/intake-data"

/** Composer draft when opening an intake item with Copilot (user edits before send). */
export function buildIntakeChatDraft(item: IntakeItem, cluster?: IntakeCluster): string {
  const lines = [
    `Help me handle this intake request.`,
    ``,
    `Request ID: ${item.id}`,
    `Subject: ${item.subject}`,
    `Topic: ${item.topic}`,
    cluster ? `Cluster: ${cluster.label} (${cluster.domain})` : null,
    `Channel: ${channelMeta[item.channel]}`,
    `Urgency: ${item.urgency}`,
    `State: ${item.state}`,
    `Disposition: ${dispositionMeta[item.disposition].label}`,
    `Confidence: ${Math.round(item.confidence * 100)}%`,
    `Age: ${item.age}`,
    `Due: ${item.due}`,
    ``,
    `Requester: ${item.requester.name} (${item.requester.role})`,
    ``,
    `Request excerpt:`,
    item.snippet,
    ``,
    `Copilot suggestion:`,
    item.suggestion,
    ``,
    `Please propose next steps.`,
  ]
  return lines.filter((l) => l !== null).join("\n")
}

function intakeTicketBlock(item: IntakeItem, cluster?: IntakeCluster): string {
  return [
    `Ticket ID: ${item.id}`,
    `Subject: ${item.subject}`,
    `Topic: ${item.topic}`,
    cluster ? `Current cluster: ${cluster.label}` : null,
    `Channel: ${channelMeta[item.channel]}`,
    `Urgency: ${item.urgency}`,
    `Requester: ${item.requester.name} (${item.requester.role})`,
    ``,
    `Excerpt:`,
    item.snippet,
    ``,
    `Suggestion on file:`,
    item.suggestion,
  ]
    .filter((l) => l !== null)
    .join("\n")
}

/** Draft: email this ticket to a department (optional To; else look up from DB). */
export function buildIntakeRouteDraft(
  item: IntakeItem,
  opts: { departmentLabel: string; email?: string; note?: string; cluster?: IntakeCluster },
): string {
  const to = opts.email?.trim() || ""
  const lines = [
    `Email this intake ticket to the ${opts.departmentLabel} department.`,
    ``,
    `To: ${to}`,
    to
      ? `Use the To address above.`
      : `No email was provided — look up the ${opts.departmentLabel} distribution / queue mailbox from the HR directory or employee database and use that address.`,
    ``,
    `Include the ticket details below in the email body. Draft a clear subject and message, then prepare send_email for my approval.`,
    opts.note?.trim() ? `` : null,
    opts.note?.trim() ? `Note from triage: ${opts.note.trim()}` : null,
    ``,
    `--- Ticket ---`,
    intakeTicketBlock(item, opts.cluster),
  ]
  return lines.filter((l) => l !== null).join("\n")
}

/** Draft: group/reassign ticket into a cluster and notify owners (optional To; else DB). */
export function buildIntakeGroupDraft(
  item: IntakeItem,
  opts: { groupLabel: string; email?: string; note?: string; cluster?: IntakeCluster },
): string {
  const to = opts.email?.trim() || ""
  const lines = [
    `Group / reassign this intake ticket into "${opts.groupLabel}" and notify the owning group.`,
    ``,
    `To: ${to}`,
    to
      ? `Use the To address above for the notification.`
      : `No email was provided — look up the mailbox or owners for the "${opts.groupLabel}" queue/cluster from the HR directory or employee database and notify them.`,
    ``,
    `Explain why it belongs in this group, summarize the request, and prepare the notification email for my approval.`,
    opts.note?.trim() ? `` : null,
    opts.note?.trim() ? `Note from triage: ${opts.note.trim()}` : null,
    ``,
    `--- Ticket ---`,
    intakeTicketBlock(item, opts.cluster),
  ]
  return lines.filter((l) => l !== null).join("\n")
}
