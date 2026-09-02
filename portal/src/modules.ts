export type ModuleId =
  | "home"
  | "directory"
  | "faq"
  | "helpdesk"
  | "hiring"
  | "training"
  | "policies"
  | "copilot";

export type ModuleDef = {
  id: ModuleId;
  path: string;
  label: string;
  blurb: string;
  status: "live" | "soon";
  servicePort?: number;
};

export const MODULES: ModuleDef[] = [
  {
    id: "home",
    path: "/",
    label: "Home",
    blurb: "Portal overview",
    status: "live",
  },
  {
    id: "directory",
    path: "/directory",
    label: "Directory",
    blurb: "People search and org profiles (Mel)",
    status: "live",
    servicePort: 8101,
  },
  {
    id: "faq",
    path: "/faq",
    label: "FAQ",
    blurb: "Policy Q&A chatbot",
    status: "soon",
    servicePort: 8107,
  },
  {
    id: "helpdesk",
    path: "/helpdesk",
    label: "Helpdesk",
    blurb: "Tickets, leave, onboarding",
    status: "soon",
    servicePort: 8103,
  },
  {
    id: "hiring",
    path: "/hiring",
    label: "Hiring",
    blurb: "Resume screening and pipelines",
    status: "soon",
    servicePort: 8102,
  },
  {
    id: "training",
    path: "/training",
    label: "Training",
    blurb: "Compliance pathways and quizzes",
    status: "soon",
    servicePort: 8104,
  },
  {
    id: "policies",
    path: "/policies",
    label: "Policies",
    blurb: "AI policy generator",
    status: "soon",
    servicePort: 8106,
  },
  {
    id: "copilot",
    path: "/copilot",
    label: "Copilot",
    blurb: "Vera — AI HR Copilot",
    status: "soon",
    servicePort: 8105,
  },
];
