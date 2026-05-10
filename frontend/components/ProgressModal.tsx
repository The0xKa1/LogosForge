"use client";

import { useEffect, useState } from "react";
import { Loader2, CheckCircle2, Circle } from "lucide-react";

export interface ProgressStep {
  label: string;
  detail?: string;
}

interface ProgressModalProps {
  title: string;
  steps: ProgressStep[];
  currentStep: number;
  error?: string | null;
  onCancel?: () => void;
}

export function ProgressModal({ title, steps, currentStep, error, onCancel }: ProgressModalProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  };

  const progress = steps.length > 0 ? ((currentStep + 1) / steps.length) * 100 : 0;

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="modal-header">
          <h3>{title}</h3>
          <span className="modal-timer">{formatTime(elapsed)}</span>
        </div>

        <div className="progress-bar-track">
          <div
            className="progress-bar-fill"
            style={{ width: `${Math.min(progress, 100)}%` }}
          />
        </div>

        <div className="step-list">
          {steps.map((step, i) => {
            const isDone = i < currentStep;
            const isCurrent = i === currentStep;
            const isError = error && i === currentStep;

            return (
              <div key={i} className={`step-item ${isDone ? "done" : ""} ${isCurrent ? "current" : ""} ${isError ? "error" : ""}`}>
                <span className="step-icon">
                  {isDone ? (
                    <CheckCircle2 size={18} />
                  ) : isCurrent && !error ? (
                    <Loader2 size={18} className="spin" />
                  ) : (
                    <Circle size={18} />
                  )}
                </span>
                <div className="step-text">
                  <span className="step-label">{step.label}</span>
                  {step.detail && isCurrent && <span className="step-detail">{step.detail}</span>}
                  {isError && <span className="step-detail error-text">{error}</span>}
                </div>
              </div>
            );
          })}
        </div>

        {error && onCancel && (
          <button className="modal-cancel" onClick={onCancel}>
            关闭
          </button>
        )}
      </div>
    </div>
  );
}
