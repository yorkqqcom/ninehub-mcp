import { describe, expect, it } from "vitest";
import {
  allowedSteps,
  canGoBack,
  canGoToStep,
  nextStep,
  prevStep,
  stepFromJobStatus,
} from "@/composables/useWizardState";

describe("useWizardState", () => {
  it("allowedSteps differs by mode", () => {
    expect(allowedSteps("full")).toEqual([1, 2, 3, 4, 5, 6]);
    expect(allowedSteps("quick")).toEqual([1, 4, 5, 6]);
  });

  it("blocks back during running job on step 4", () => {
    expect(canGoBack(4, "running")).toBe(false);
    expect(canGoBack(4, "completed")).toBe(true);
  });

  it("next/prev for full mode", () => {
    expect(nextStep(1, { mode: "full" })).toBe(2);
    expect(nextStep(5, { mode: "full" })).toBe(6);
    expect(prevStep(3, { mode: "full" })).toBe(2);
  });

  it("prev for quick mode from step 6", () => {
    expect(prevStep(6, { mode: "quick" })).toBe(5);
    expect(prevStep(4, { mode: "quick" })).toBe(1);
  });

  it("stepFromJobStatus maps job lifecycle", () => {
    expect(stepFromJobStatus("running", "full")).toBe(4);
    expect(stepFromJobStatus("completed", "full", 6)).toBe(6);
    expect(stepFromJobStatus("failed", "quick")).toBe(4);
  });

  it("canGoToStep respects running job lock", () => {
    expect(
      canGoToStep(3, {
        mode: "full",
        currentStep: 4,
        jobId: "j1",
        jobStatus: "running",
      }),
    ).toBe(false);
    expect(
      canGoToStep(4, {
        mode: "full",
        currentStep: 4,
        jobId: "j1",
        jobStatus: "running",
      }),
    ).toBe(true);
  });
});
