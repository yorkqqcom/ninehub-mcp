/** Pure wizard step transitions — unit-testable. */

export type WizardMode = "quick" | "full";

export type WizardContext = {
  mode: WizardMode;
  jobStatus?: string | null;
};

export function allowedSteps(mode: WizardMode): number[] {
  return mode === "quick" ? [1, 4, 5, 6] : [1, 2, 3, 4, 5, 6];
}

export function canGoBack(step: number, jobStatus?: string | null): boolean {
  if (step === 4 && (jobStatus === "pending" || jobStatus === "running")) {
    return false;
  }
  return step > 1;
}

export function nextStep(from: number, ctx: WizardContext): number | null {
  if (ctx.mode === "quick") {
    if (from === 5) return 6;
    return null;
  }
  if (from === 1) return 2;
  if (from === 2) return 3;
  if (from === 5) return 6;
  return null;
}

export function prevStep(from: number, ctx: WizardContext): number | null {
  if (!canGoBack(from, ctx.jobStatus)) return null;
  if (ctx.mode === "quick") {
    if (from === 6) return 5;
    if (from === 5) return 4;
    if (from === 4) return 1;
    return null;
  }
  if (from === 6) return 5;
  if (from === 5) return 4;
  if (from === 4) return 3;
  if (from === 3) return 2;
  if (from === 2) return 1;
  return null;
}

/** Map build job status (+ optional URL step) to wizard step when restoring from route. */
export function stepFromJobStatus(
  status: string,
  mode: WizardMode,
  routeStep?: number,
): number {
  if (status === "pending" || status === "running") return 4;
  if (status === "failed") return 4;
  if (status === "completed") {
    if (routeStep && routeStep >= 6) return 6;
    if (routeStep && routeStep === 5) return 5;
    return 5;
  }
  return mode === "quick" ? 1 : 1;
}

export function canGoToStep(
  target: number,
  ctx: WizardContext & { currentStep: number; jobId?: string | null },
): boolean {
  if (!allowedSteps(ctx.mode).includes(target)) return false;
  if (
    ctx.jobId &&
    (ctx.jobStatus === "pending" || ctx.jobStatus === "running") &&
    target !== 4
  ) {
    return false;
  }
  return target <= ctx.currentStep;
}

export function displayStepNumber(step: number, mode: WizardMode): number {
  return step;
}

export function stepperItems(mode: WizardMode): { n: number; label: string }[] {
  if (mode === "quick") {
    return [
      { n: 1, label: "选连接" },
      { n: 4, label: "构建" },
      { n: 5, label: "预览" },
      { n: 6, label: "完成" },
    ];
  }
  return [
    { n: 1, label: "选连接" },
    { n: 2, label: "审视" },
    { n: 3, label: "策略" },
    { n: 4, label: "构建" },
    { n: 5, label: "预览" },
    { n: 6, label: "完成" },
  ];
}
