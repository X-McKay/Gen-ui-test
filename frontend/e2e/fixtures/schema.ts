import fs from "node:fs";
import path from "node:path";

import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";

const SCHEMA_PATH = path.resolve(__dirname, "../../../schema/intake.schema.json");

let compiled: ReturnType<Ajv2020["compile"]> | null = null;

function validator(): ReturnType<Ajv2020["compile"]> {
  if (compiled) return compiled;
  const schema = JSON.parse(fs.readFileSync(SCHEMA_PATH, "utf8")) as Record<string, unknown>;
  const ajv = new Ajv2020({ allErrors: true, strict: false });
  addFormats(ajv);
  compiled = ajv.compile(schema);
  return compiled;
}

/** Validate a JSON export against `schema/intake.schema.json` (draft 2020-12). */
export function validateIntakeDocument(document: unknown): { valid: boolean; errors: string[] } {
  const validate = validator();
  const valid = validate(document) === true;
  const errors = (validate.errors ?? []).map(
    (error) => `${error.instancePath || "/"} ${error.message ?? ""} ${JSON.stringify(error.params)}`,
  );
  return { valid, errors };
}
