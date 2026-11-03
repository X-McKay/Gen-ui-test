"use client";

/**
 * Form state shared between an `InterviewStep` and the question / assumption / findings
 * components rendered into its slots. Questions register themselves; the step owns the
 * single confirm button and submits everything as one action.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export const NOT_SURE = "unknown" as const;

export interface FieldRegistration {
  required: boolean;
  valid: boolean;
}

export interface InterviewFormValue {
  /** Answers to questions, by field path. `"unknown"` means Not sure. */
  answers: Record<string, unknown>;
  /** Assumption chips and findings, by field path, with their (possibly edited) value. */
  assumptions: Record<string, unknown>;
  setAnswer: (field: string, value: unknown) => void;
  setAssumption: (field: string, value: unknown) => void;
  register: (field: string, registration: FieldRegistration) => void;
  unregister: (field: string) => void;
  submitting: boolean;
  stepKey: string;
}

const InterviewFormContext = createContext<InterviewFormValue | null>(null);

export function useInterviewForm(): InterviewFormValue | null {
  return useContext(InterviewFormContext);
}

function storageKey(stepKey: string): string {
  return `intake:draft:${stepKey}`;
}

function readDraft(stepKey: string): Record<string, unknown> {
  try {
    const raw = window.localStorage.getItem(storageKey(stepKey));
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    return typeof parsed === "object" && parsed !== null ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function writeDraft(stepKey: string, answers: Record<string, unknown>): void {
  try {
    window.localStorage.setItem(storageKey(stepKey), JSON.stringify(answers));
  } catch {
    /* storage may be unavailable; the draft is a convenience only */
  }
}

export function clearDraft(stepKey: string): void {
  try {
    window.localStorage.removeItem(storageKey(stepKey));
  } catch {
    /* ignore */
  }
}

interface ProviderProps {
  stepKey: string;
  submitting: boolean;
  children: ReactNode;
  onChange?: (state: { complete: boolean; count: number }) => void;
}

export function InterviewFormProvider({ stepKey, submitting, children, onChange }: ProviderProps) {
  const [answers, setAnswers] = useState<Record<string, unknown>>(() =>
    typeof window === "undefined" ? {} : readDraft(stepKey),
  );
  const [assumptions, setAssumptions] = useState<Record<string, unknown>>({});
  const [registrations, setRegistrations] = useState<Record<string, FieldRegistration>>({});
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    writeDraft(stepKey, answers);
  }, [stepKey, answers]);

  const setAnswer = useCallback((field: string, value: unknown) => {
    setAnswers((previous) => ({ ...previous, [field]: value }));
  }, []);
  const setAssumption = useCallback((field: string, value: unknown) => {
    setAssumptions((previous) => ({ ...previous, [field]: value }));
  }, []);
  const register = useCallback((field: string, registration: FieldRegistration) => {
    setRegistrations((previous) => {
      const current = previous[field];
      if (current && current.required === registration.required && current.valid === registration.valid) {
        return previous;
      }
      return { ...previous, [field]: registration };
    });
  }, []);
  const unregister = useCallback((field: string) => {
    setRegistrations((previous) => {
      if (!(field in previous)) return previous;
      const next = { ...previous };
      delete next[field];
      return next;
    });
  }, []);

  const complete = useMemo(
    () => Object.values(registrations).every((registration) => registration.valid),
    [registrations],
  );
  useEffect(() => {
    onChangeRef.current?.({ complete, count: Object.keys(registrations).length });
  }, [complete, registrations]);

  const value = useMemo<InterviewFormValue>(
    () => ({ answers, assumptions, setAnswer, setAssumption, register, unregister, submitting, stepKey }),
    [answers, assumptions, setAnswer, setAssumption, register, unregister, submitting, stepKey],
  );
  return <InterviewFormContext.Provider value={value}>{children}</InterviewFormContext.Provider>;
}

/** Register one question with the step and read/write its answer. */
export function useInterviewField<T>(
  field: string,
  options: { required: boolean; validate?: (value: T | typeof NOT_SURE | undefined) => boolean },
): [T | typeof NOT_SURE | undefined, (value: T | typeof NOT_SURE | undefined) => void] {
  const form = useInterviewForm();
  const [local, setLocal] = useState<T | typeof NOT_SURE | undefined>(undefined);
  const value = (form ? (form.answers[field] as T | typeof NOT_SURE | undefined) : local) ?? undefined;
  const { required, validate } = options;
  const valid = useMemo(() => {
    if (value === undefined) return !required;
    if (value === NOT_SURE) return true;
    return validate ? validate(value) : true;
  }, [value, required, validate]);
  useEffect(() => {
    form?.register(field, { required, valid });
  }, [form, field, required, valid]);
  useEffect(() => () => form?.unregister(field), [form, field]);
  const setValue = useCallback(
    (next: T | typeof NOT_SURE | undefined) => {
      if (form) form.setAnswer(field, next);
      else setLocal(next);
    },
    [form, field],
  );
  return [value, setValue];
}
