/**
 * Static labels and control metadata for every record field.
 *
 * Copied from `backend/app/intake/question_bank.py` so chips, the review page and the
 * PDF say the same thing. Keep the two in sync when a question changes.
 */

export type SectionKey = "project" | "ai_system" | "data" | "use_case";
export type ControlKind = "choice" | "multi" | "yes_no" | "text";

export interface OptionSpec {
  value: string;
  label: string;
}

export interface FieldSpec {
  field: string;
  section: SectionKey;
  label: string;
  prompt: string;
  control: ControlKind;
  options: readonly OptionSpec[];
  required: boolean;
  mustConfirm: boolean;
  isGate: boolean;
  sensitive: boolean;
  whyAsked: string | null;
  placeholder: string | null;
}

export const SECTION_LABELS: Record<SectionKey, string> = {
  project: "Project",
  ai_system: "AI system",
  data: "Data",
  use_case: "Use case",
};

export const SECTION_ORDER: readonly SectionKey[] = ["project", "ai_system", "data", "use_case"];

const opts = (...pairs: readonly (readonly [string, string])[]): OptionSpec[] =>
  pairs.map(([value, label]) => ({ value, label }));

type SpecInput = Pick<FieldSpec, "field" | "section" | "label" | "prompt" | "control"> &
  Partial<Omit<FieldSpec, "field" | "section" | "label" | "prompt" | "control">>;

const spec = (input: SpecInput): FieldSpec => ({
  options: [],
  required: true,
  mustConfirm: false,
  isGate: false,
  sensitive: false,
  whyAsked: null,
  placeholder: null,
  ...input,
});

/** Every question in the bank, in record order within each section. */
export const FIELD_SPECS: readonly FieldSpec[] = [
  // --- Project --------------------------------------------------------------------------
  spec({
    field: "project.name",
    section: "project",
    label: "Project name",
    prompt: "What is the project called?",
    control: "text",
    placeholder: "Candidate summary assistant",
  }),
  spec({
    field: "project.description",
    section: "project",
    label: "Description",
    prompt: "Describe the project in a sentence or two.",
    control: "text",
    required: false,
  }),
  spec({
    field: "project.owner",
    section: "project",
    label: "Owner",
    prompt: "Who owns the project?",
    control: "text",
    placeholder: "Name or team alias",
  }),
  spec({
    field: "project.team",
    section: "project",
    label: "Team",
    prompt: "Which team builds it?",
    control: "text",
    required: false,
  }),
  spec({
    field: "project.business_unit",
    section: "project",
    label: "Business unit",
    prompt: "Which business unit does it belong to?",
    control: "text",
    required: false,
  }),
  spec({
    field: "project.lifecycle_stage",
    section: "project",
    label: "Lifecycle stage",
    prompt: "Where is the project in its lifecycle?",
    control: "choice",
    options: opts(["idea", "Idea"], ["poc", "Proof of concept"], ["pilot", "Pilot"], ["production", "Production"]),
  }),
  spec({
    field: "project.target_users",
    section: "project",
    label: "Target users",
    prompt: "Who will use it?",
    control: "choice",
    options: opts(
      ["internal", "Internal staff"],
      ["external", "External partners or customers"],
      ["public", "The general public"],
    ),
  }),
  spec({
    field: "project.deployment_regions",
    section: "project",
    label: "Deployment regions",
    prompt: "Where will it be deployed?",
    control: "multi",
    options: opts(
      ["eu", "European Union"],
      ["uk", "United Kingdom"],
      ["us", "United States"],
      ["apac", "Asia-Pacific"],
      ["global", "Global"],
    ),
    required: false,
  }),
  // --- AI system ------------------------------------------------------------------------
  spec({
    field: "ai_system.uses_ai",
    section: "ai_system",
    label: "Uses AI",
    prompt: "Does the project use a machine-learning or generative model?",
    control: "yes_no",
    isGate: true,
  }),
  spec({
    field: "ai_system.model_types",
    section: "ai_system",
    label: "Model types",
    prompt: "What kind of models are involved?",
    control: "multi",
    options: opts(
      ["llm", "Large language model"],
      ["vision", "Computer vision"],
      ["speech", "Speech or audio"],
      ["classical_ml", "Classical ML (scoring, forecasting)"],
      ["recommender", "Recommender"],
      ["other", "Other"],
    ),
    required: false,
  }),
  spec({
    field: "ai_system.model_source",
    section: "ai_system",
    label: "Model source",
    prompt: "Where does the model come from?",
    control: "choice",
    options: opts(
      ["third_party_api", "Third-party API"],
      ["open_weights", "Open weights, self-hosted"],
      ["in_house", "Trained in house"],
    ),
  }),
  spec({
    field: "ai_system.model_providers",
    section: "ai_system",
    label: "Model providers",
    prompt: "Which model providers are used?",
    control: "multi",
    options: opts(
      ["openai", "OpenAI"],
      ["anthropic", "Anthropic"],
      ["google", "Google"],
      ["aws_bedrock", "AWS Bedrock"],
      ["azure_openai", "Azure OpenAI"],
      ["mistral", "Mistral"],
      ["meta", "Meta (Llama)"],
      ["self_hosted", "Self-hosted"],
      ["other", "Other"],
    ),
    required: false,
  }),
  spec({
    field: "ai_system.gpai_model_used",
    section: "ai_system",
    label: "General-purpose model",
    prompt: "Is a general-purpose model (for example an LLM) part of it?",
    control: "yes_no",
  }),
  spec({
    field: "ai_system.fine_tuned_or_trained",
    section: "ai_system",
    label: "Fine-tuned or trained",
    prompt: "Do you fine-tune or train the model yourselves?",
    control: "yes_no",
    required: false,
  }),
  spec({
    field: "ai_system.autonomy_level",
    section: "ai_system",
    label: "Autonomy",
    prompt: "How much does the system decide on its own?",
    control: "choice",
    options: opts(
      ["assistive", "Assists a person"],
      ["recommends", "Recommends, a person decides"],
      ["decides", "Decides without review"],
    ),
    whyAsked: "Automated decisions need stronger oversight.",
  }),
  spec({
    field: "ai_system.human_oversight",
    section: "ai_system",
    label: "Human oversight",
    prompt: "Can a person review or override its outputs?",
    control: "yes_no",
  }),
  // --- Data -----------------------------------------------------------------------------
  spec({
    field: "data.processes_personal_data",
    section: "data",
    label: "Personal data",
    prompt: "Does it process personal data about identifiable people?",
    control: "yes_no",
    isGate: true,
    whyAsked: "Personal data brings GDPR into scope.",
  }),
  spec({
    field: "data.pii_categories",
    section: "data",
    label: "Personal data categories",
    prompt: "Which kinds of personal data does it process?",
    control: "multi",
    options: opts(
      ["contact", "Names and contact details"],
      ["identifiers", "IDs and account numbers"],
      ["financial", "Financial"],
      ["employment", "Employment and education history"],
      ["location", "Location"],
      ["behavioural", "Behavioural or usage"],
      ["free_text", "Free text that may contain anything"],
    ),
    required: false,
  }),
  spec({
    field: "data.special_category_data",
    section: "data",
    label: "Special-category data",
    prompt: "Does it handle any special-category data?",
    control: "multi",
    options: opts(
      ["health", "Health"],
      ["biometric", "Biometric"],
      ["ethnicity", "Ethnicity"],
      ["political", "Political opinions"],
      ["religious", "Religious beliefs"],
      ["sexual_orientation", "Sexual orientation"],
      ["criminal", "Criminal records"],
    ),
    mustConfirm: true,
    sensitive: true,
    whyAsked: "Special-category data needs a DPIA and changes the risk tier.",
  }),
  spec({
    field: "data.biometric_identification",
    section: "data",
    label: "Biometric identification",
    prompt: "Does it identify people from biometric data such as faces or voices?",
    control: "yes_no",
    mustConfirm: true,
    sensitive: true,
    whyAsked: "Biometric identification changes the EU AI Act tier.",
  }),
  spec({
    field: "data.data_subjects",
    section: "data",
    label: "Data subjects",
    prompt: "Whose data is it?",
    control: "multi",
    options: opts(
      ["employees", "Employees or candidates"],
      ["customers", "Customers"],
      ["public", "Members of the public"],
      ["minors", "Minors"],
    ),
    mustConfirm: true,
    sensitive: true,
    whyAsked: "Data about minors raises the risk tier.",
  }),
  spec({
    field: "data.data_sources",
    section: "data",
    label: "Data sources",
    prompt: "Where does the data come from?",
    control: "multi",
    options: opts(
      ["internal_db", "Internal databases"],
      ["user_upload", "User uploads"],
      ["third_party", "Third-party providers"],
      ["public_web", "Public web"],
      ["logs", "System logs"],
    ),
    required: false,
  }),
  spec({
    field: "data.trains_on_personal_data",
    section: "data",
    label: "Trains on personal data",
    prompt: "Is personal data used to train or fine-tune a model?",
    control: "yes_no",
  }),
  spec({
    field: "data.retention_policy",
    section: "data",
    label: "Retention policy",
    prompt: "How long is personal data kept?",
    control: "choice",
    options: opts(
      ["not_stored", "Not stored"],
      ["under_30_days", "Under 30 days"],
      ["under_1_year", "Under a year"],
      ["over_1_year", "A year or longer"],
      ["undefined", "No policy yet"],
    ),
    required: false,
  }),
  spec({
    field: "data.cross_border_transfer",
    section: "data",
    label: "Cross-border transfer",
    prompt: "Does personal data leave the region it was collected in?",
    control: "yes_no",
    required: false,
  }),
  // --- Use case -------------------------------------------------------------------------
  spec({
    field: "use_case.domains",
    section: "use_case",
    label: "Domains",
    prompt: "Which areas does the project operate in?",
    control: "multi",
    options: opts(
      ["hr_employment", "HR and employment"],
      ["credit_insurance", "Credit or insurance"],
      ["education", "Education"],
      ["law_enforcement", "Law enforcement"],
      ["migration_border", "Migration and border"],
      ["justice_democratic", "Justice or democratic processes"],
      ["critical_infrastructure", "Critical infrastructure"],
      ["medical_or_safety_component", "Medical or safety component"],
      ["essential_services", "Essential services"],
      ["other", "None of these"],
    ),
    isGate: true,
    mustConfirm: true,
    sensitive: true,
    whyAsked: "Several of these areas are high-risk under EU AI Act Annex III.",
  }),
  spec({
    field: "use_case.purpose",
    section: "use_case",
    label: "Purpose",
    prompt: "In one line, what is it for?",
    control: "text",
    required: false,
  }),
  spec({
    field: "use_case.affects_legal_or_significant_effects",
    section: "use_case",
    label: "Significant effects",
    prompt: "Can its output affect someone's legal rights, job, credit or access to services?",
    control: "yes_no",
    isGate: true,
    sensitive: true,
    whyAsked: "Significant effects on people raise the risk tier.",
  }),
  spec({
    field: "use_case.interacts_directly_with_people",
    section: "use_case",
    label: "Interacts with people",
    prompt: "Do people interact with the AI directly, for example through chat?",
    control: "yes_no",
    whyAsked: "Direct interaction carries a transparency obligation.",
  }),
  spec({
    field: "use_case.generates_synthetic_content",
    section: "use_case",
    label: "Generates content",
    prompt: "Does it generate text, images, audio or video shown to people?",
    control: "yes_no",
  }),
  spec({
    field: "use_case.emotion_recognition",
    section: "use_case",
    label: "Emotion recognition",
    prompt: "Does it infer emotions or intentions from people?",
    control: "yes_no",
    mustConfirm: true,
    sensitive: true,
    whyAsked: "Emotion recognition at work or school is prohibited.",
  }),
  spec({
    field: "use_case.social_scoring",
    section: "use_case",
    label: "Social scoring",
    prompt: "Does it score people on behaviour or traits to decide their treatment?",
    control: "yes_no",
    mustConfirm: true,
    sensitive: true,
    whyAsked: "Social scoring is a prohibited practice.",
  }),
  spec({
    field: "use_case.remote_biometric_id_public_spaces",
    section: "use_case",
    label: "Remote biometric ID",
    prompt: "Does it identify people remotely in public spaces?",
    control: "yes_no",
    mustConfirm: true,
    sensitive: true,
    whyAsked: "Remote biometric identification in public is tightly restricted.",
  }),
  spec({
    field: "use_case.manipulative_or_subliminal",
    section: "use_case",
    label: "Manipulative techniques",
    prompt: "Does it use subliminal or manipulative techniques to steer behaviour?",
    control: "yes_no",
    mustConfirm: true,
    sensitive: true,
    required: false,
    whyAsked: "Manipulative techniques are a prohibited practice.",
  }),
  spec({
    field: "use_case.untargeted_facial_scraping",
    section: "use_case",
    label: "Facial-image scraping",
    prompt: "Does it collect facial images from the web or CCTV at scale?",
    control: "yes_no",
    mustConfirm: true,
    sensitive: true,
    required: false,
    whyAsked: "Untargeted facial scraping is a prohibited practice.",
  }),
];

export const FIELD_SPECS_BY_PATH: Readonly<Record<string, FieldSpec>> = Object.fromEntries(
  FIELD_SPECS.map((s) => [s.field, s]),
);

/** Field path → short label, e.g. `"data.processes_personal_data"` → `"Personal data"`. */
export const FIELD_LABELS: Readonly<Record<string, string>> = Object.fromEntries(
  FIELD_SPECS.map((s) => [s.field, s.label]),
);

/** Field path → how it is edited. */
export const FIELD_CONTROLS: Readonly<Record<string, ControlKind>> = Object.fromEntries(
  FIELD_SPECS.map((s) => [s.field, s.control]),
);

/** Field path → selectable options (empty for yes/no and text). */
export const FIELD_OPTIONS: Readonly<Record<string, readonly OptionSpec[]>> = Object.fromEntries(
  FIELD_SPECS.map((s) => [s.field, s.options]),
);

/**
 * Option value → label, keyed by field path then value. Values are not globally unique
 * (`other`, `public`), so the lookup is always scoped to a field.
 */
export const OPTION_LABELS: Readonly<Record<string, Readonly<Record<string, string>>>> = Object.fromEntries(
  FIELD_SPECS.map((s) => [s.field, Object.fromEntries(s.options.map((o) => [o.value, o.label]))]),
);

/** Section → its fields, in record order. */
export const SECTION_FIELDS: Readonly<Record<SectionKey, readonly string[]>> = {
  project: FIELD_SPECS.filter((s) => s.section === "project").map((s) => s.field),
  ai_system: FIELD_SPECS.filter((s) => s.section === "ai_system").map((s) => s.field),
  data: FIELD_SPECS.filter((s) => s.section === "data").map((s) => s.field),
  use_case: FIELD_SPECS.filter((s) => s.section === "use_case").map((s) => s.field),
};

export const MUST_CONFIRM_FIELDS: ReadonlySet<string> = new Set(
  FIELD_SPECS.filter((s) => s.mustConfirm).map((s) => s.field),
);

/** Human label for a field path; falls back to a readable version of the last segment. */
export function fieldLabel(path: string): string {
  const known = FIELD_LABELS[path];
  if (known) return known;
  const last = path.split(".").pop() ?? path;
  const words = last.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function sectionOf(path: string): SectionKey | null {
  const head = path.split(".")[0];
  return (SECTION_ORDER as readonly string[]).includes(head) ? (head as SectionKey) : null;
}

/** Label for an option value within a field; falls back to the raw value. */
export function optionLabel(path: string, value: string): string {
  return OPTION_LABELS[path]?.[value] ?? value;
}

export const TIER_LABELS = {
  prohibited: "Prohibited",
  high_risk: "High risk",
  limited_transparency: "Limited risk — transparency",
  minimal: "Minimal risk",
} as const;

export type TierKey = keyof typeof TIER_LABELS;

/** One plain-language sentence per tier, shown under the badge on the review page. */
export const TIER_EXPLANATIONS: Record<TierKey, string> = {
  prohibited: "The described practice is banned under Article 5. It cannot be placed on the market or used in the EU.",
  high_risk: "Systems in this area are listed in Annex III. Provider and deployer obligations apply before deployment.",
  limited_transparency:
    "People must be told they are dealing with AI or AI-generated content under Article 50. No conformity assessment is required.",
  minimal: "No specific EU AI Act obligations apply. Voluntary codes of practice are encouraged.",
};

export const RISK_TIER_LABELS: Record<"low" | "medium" | "high" | "critical", string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

export const FRAMEWORK_LABELS: Readonly<Record<string, string>> = {
  eu_ai_act: "EU AI Act",
  gdpr: "GDPR",
  nist_ai_rmf: "NIST AI RMF",
  iso_42001: "ISO/IEC 42001",
  internal_policy: "Internal policy",
};

export function frameworkLabel(key: string): string {
  return FRAMEWORK_LABELS[key] ?? FRAMEWORK_LABELS[key.toLowerCase()] ?? key;
}

export const ANNEX_III_LABELS: Readonly<Record<string, string>> = {
  hr_employment: "Employment, workers management and access to self-employment",
  credit_insurance: "Access to essential private services: credit and insurance",
  education: "Education and vocational training",
  law_enforcement: "Law enforcement",
  migration_border: "Migration, asylum and border control",
  justice_democratic: "Administration of justice and democratic processes",
  critical_infrastructure: "Critical infrastructure",
  medical_or_safety_component: "Safety component of a product",
  essential_services: "Access to essential public services and benefits",
  biometrics: "Biometrics",
};

export function annexLabel(key: string): string {
  return ANNEX_III_LABELS[key] ?? optionLabel("use_case.domains", key);
}
