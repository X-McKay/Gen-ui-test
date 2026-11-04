/* Generated from schema/intake.schema.json by pnpm gen:types. Do not edit. */

export type IntakeId = string;
export type SchemaVersion = string;
export type IntakeMode = "new" | "existing";
export type IntakeStatus = "in_progress" | "completed" | "submitted" | "escalated";
export type RepoUrl = string | null;
export type CreatedAt = string;
export type UpdatedAt = string;
export type CompletedAt = string | null;
export type SubmittedAt = string | null;
export type QuestionCount = number;
export type AnalysisProgress = string | null;
export type Value = string | "unknown" | null;
export type Confidence = number;
export type Source = string;
export type Confirmed = boolean;
export type Value1 = LifecycleStage | "unknown" | null;
export type LifecycleStage = "idea" | "poc" | "pilot" | "production";
export type Confidence1 = number;
export type Source1 = string;
export type Confirmed1 = boolean;
export type Value2 = TargetUsers | "unknown" | null;
export type TargetUsers = "internal" | "external" | "public";
export type Confidence2 = number;
export type Source2 = string;
export type Confirmed2 = boolean;
export type Value3 = string[] | "unknown" | null;
export type Confidence3 = number;
export type Source3 = string;
export type Confirmed3 = boolean;
export type Value4 = boolean | "unknown" | null;
export type Confidence4 = number;
export type Source4 = string;
export type Confirmed4 = boolean;
export type Value5 = ModelSource | "unknown" | null;
export type ModelSource = "third_party_api" | "open_weights" | "in_house";
export type Confidence5 = number;
export type Source5 = string;
export type Confirmed5 = boolean;
export type Value6 = AutonomyLevel | "unknown" | null;
export type AutonomyLevel = "assistive" | "recommends" | "decides";
export type Confidence6 = number;
export type Source6 = string;
export type Confirmed6 = boolean;
export type Value7 = SpecialCategory[] | "unknown" | null;
export type SpecialCategory =
  "health" | "biometric" | "ethnicity" | "political" | "religious" | "sexual_orientation" | "criminal";
export type Confidence7 = number;
export type Source7 = string;
export type Confirmed7 = boolean;
export type Value8 = DataSubject[] | "unknown" | null;
export type DataSubject = "employees" | "customers" | "public" | "minors";
export type Confidence8 = number;
export type Source8 = string;
export type Confirmed8 = boolean;
export type Value9 = Domain[] | "unknown" | null;
export type Domain =
  | "hr_employment"
  | "credit_insurance"
  | "education"
  | "law_enforcement"
  | "migration_border"
  | "justice_democratic"
  | "critical_infrastructure"
  | "medical_or_safety_component"
  | "essential_services"
  | "other";
export type Confidence9 = number;
export type Source9 = string;
export type Confirmed9 = boolean;
export type Value10 = ControlKind[] | "unknown" | null;
/**
 * Controls the owner can declare. ``NONE`` is an explicit "none of these yet".
 */
export type ControlKind =
  | "guardrails"
  | "access_controls"
  | "pii_minimisation"
  | "abuse_monitoring"
  | "pre_release_evaluation"
  | "vendor_data_protections"
  | "incident_response"
  | "user_disclosure"
  | "none";
export type Confidence10 = number;
export type Source10 = string;
export type Confirmed10 = boolean;
export type EuAiActClassification = "prohibited" | "high_risk" | "limited_transparency" | "minimal";
export type AnnexIiiCategories = string[];
/**
 * Dotted path of the field that triggered the rule
 */
export type Field = string;
/**
 * Citation, e.g. 'EU AI Act Art. 6(2), Annex III 4'
 */
export type Article = string;
/**
 * Plain-language explanation
 */
export type Text = string;
/**
 * Classification effect, e.g. 'high_risk'
 */
export type Effect = string;
export type Rationale = RationaleEntry[];
export type RiskTier = "low" | "medium" | "high" | "critical";
/**
 * None for the overall profile
 */
export type Lens = string | null;
export type RiskTier1 = "low" | "medium" | "high" | "critical";
export type Score = number;
export type Field1 = string;
/**
 * exposure, autonomy, data or impact
 */
export type Category = string;
export type Points = number;
export type Text1 = string;
/**
 * Enterprise risk lenses this driver counts towards
 */
export type Lenses = string[];
export type Drivers = RiskDriver[];
export type Field2 = string;
/**
 * A ControlKind value, or the field name for an answer
 */
export type Control = string;
export type Status = "applied" | "unconfirmed" | "absent" | "unknown";
/**
 * Points removed from the inherent score
 */
export type Points1 = number;
export type Text2 = string;
export type Controls1 = ControlEffect[];
export type RiskTier2 = "low" | "medium" | "high" | "critical";
export type FloorReason = string | null;
export type Lens1 = string;
export type Label = string;
/**
 * Inherent and residual risk per enterprise lens, in a fixed order
 */
export type RiskLenses = RiskLens[];
export type ApplicableFrameworks = string[];
export type Framework = string;
export type Text3 = string;
export type Reference = string | null;
export type Role = ("provider" | "deployer" | "both") | null;
export type Obligations = Obligation[];
export type RecommendedNextSteps = string[];
/**
 * Dotted paths of fields left 'unknown'
 */
export type OpenQuestions = string[];

export interface IntakeRecord {
  $schema?: string;
  meta: Meta;
  project: Project;
  ai_system: AiSystem;
  data: Data;
  use_case: UseCase;
  controls: Controls;
  assessment: Assessment;
}
export interface Meta {
  intake_id: IntakeId;
  schema_version: SchemaVersion;
  mode: IntakeMode;
  status: IntakeStatus;
  repo_url: RepoUrl;
  created_at: CreatedAt;
  updated_at: UpdatedAt;
  completed_at: CompletedAt;
  submitted_at: SubmittedAt;
  question_count: QuestionCount;
  analysis_progress: AnalysisProgress;
}
export interface Project {
  name: FieldMetaStr;
  description: FieldMetaStr;
  owner: FieldMetaStr;
  team: FieldMetaStr;
  business_unit: FieldMetaStr;
  lifecycle_stage: FieldMetaLifecycleStage;
  target_users: FieldMetaTargetUsers;
  deployment_regions: FieldMetaListStr;
  third_party_services: FieldMetaStr;
}
export interface FieldMetaStr {
  value: Value;
  confidence: Confidence;
  source: Source;
  confirmed: Confirmed;
}
export interface FieldMetaLifecycleStage {
  value: Value1;
  confidence: Confidence1;
  source: Source1;
  confirmed: Confirmed1;
}
export interface FieldMetaTargetUsers {
  value: Value2;
  confidence: Confidence2;
  source: Source2;
  confirmed: Confirmed2;
}
export interface FieldMetaListStr {
  value: Value3;
  confidence: Confidence3;
  source: Source3;
  confirmed: Confirmed3;
}
export interface AiSystem {
  uses_ai: FieldMetaBool;
  model_types: FieldMetaListStr;
  model_source: FieldMetaModelSource;
  model_providers: FieldMetaListStr;
  gpai_model_used: FieldMetaBool;
  fine_tuned_or_trained: FieldMetaBool;
  autonomy_level: FieldMetaAutonomyLevel;
  human_oversight: FieldMetaBool;
}
export interface FieldMetaBool {
  value: Value4;
  confidence: Confidence4;
  source: Source4;
  confirmed: Confirmed4;
}
export interface FieldMetaModelSource {
  value: Value5;
  confidence: Confidence5;
  source: Source5;
  confirmed: Confirmed5;
}
export interface FieldMetaAutonomyLevel {
  value: Value6;
  confidence: Confidence6;
  source: Source6;
  confirmed: Confirmed6;
}
export interface Data {
  processes_personal_data: FieldMetaBool;
  pii_categories: FieldMetaListStr;
  special_category_data: FieldMetaListSpecialCategory;
  biometric_identification: FieldMetaBool;
  data_subjects: FieldMetaListDataSubject;
  data_sources: FieldMetaListStr;
  trains_on_personal_data: FieldMetaBool;
  retention_policy: FieldMetaStr;
  cross_border_transfer: FieldMetaBool;
}
export interface FieldMetaListSpecialCategory {
  value: Value7;
  confidence: Confidence7;
  source: Source7;
  confirmed: Confirmed7;
}
export interface FieldMetaListDataSubject {
  value: Value8;
  confidence: Confidence8;
  source: Source8;
  confirmed: Confirmed8;
}
export interface UseCase {
  domains: FieldMetaListDomain;
  purpose: FieldMetaStr;
  affects_legal_or_significant_effects: FieldMetaBool;
  interacts_directly_with_people: FieldMetaBool;
  generates_synthetic_content: FieldMetaBool;
  emotion_recognition: FieldMetaBool;
  social_scoring: FieldMetaBool;
  remote_biometric_id_public_spaces: FieldMetaBool;
  manipulative_or_subliminal: FieldMetaBool;
  untargeted_facial_scraping: FieldMetaBool;
}
export interface FieldMetaListDomain {
  value: Value9;
  confidence: Confidence9;
  source: Source9;
  confirmed: Confirmed9;
}
/**
 * Mitigations already in place. Only confirmed controls lower the residual risk.
 */
export interface Controls {
  in_place: FieldMetaListControlKind;
}
export interface FieldMetaListControlKind {
  value: Value10;
  confidence: Confidence10;
  source: Source10;
  confirmed: Confirmed10;
}
export interface Assessment {
  eu_ai_act: EuAiActAssessment;
  overall_risk_tier: RiskTier;
  inherent_risk: RiskProfile;
  residual_risk: RiskProfile;
  risk_lenses: RiskLenses;
  applicable_frameworks: ApplicableFrameworks;
  obligations: Obligations;
  recommended_next_steps: RecommendedNextSteps;
  open_questions: OpenQuestions;
}
export interface EuAiActAssessment {
  classification: EuAiActClassification;
  annex_iii_categories: AnnexIiiCategories;
  rationale: Rationale;
}
/**
 * Why a classification was reached, linked to the answer that drove it.
 */
export interface RationaleEntry {
  field: Field;
  value: Value11;
  article: Article;
  text: Text;
  effect: Effect;
}
/**
 * The value that triggered the rule
 */
export interface Value11 {
  [k: string]: unknown;
}
/**
 * Inherent risk (from the answers) or residual risk (after confirmed controls), for the
 * whole use case or for one enterprise risk lens.
 */
export interface RiskProfile {
  lens: Lens;
  tier: RiskTier1;
  score: Score;
  drivers: Drivers;
  controls: Controls1;
  floor: RiskTier2 | null;
  floor_reason: FloorReason;
}
/**
 * One answer that adds inherent risk, with the points it contributes.
 */
export interface RiskDriver {
  field: Field1;
  value: Value12;
  category: Category;
  points: Points;
  text: Text1;
  lenses: Lenses;
}
export interface Value12 {
  [k: string]: unknown;
}
/**
 * What one control did to the residual score, and why it did or did not count.
 */
export interface ControlEffect {
  field: Field2;
  control: Control;
  status: Status;
  points: Points1;
  text: Text2;
}
/**
 * One enterprise lens (data privacy, information security, operational, financial,
 * reputational, regulatory) with its inherent and residual profile.
 */
export interface RiskLens {
  lens: Lens1;
  label: Label;
  inherent: RiskProfile;
  residual: RiskProfile;
}
export interface Obligation {
  framework: Framework;
  text: Text3;
  reference: Reference;
  role: Role;
}
