"use client";

import React from "react";
import { translate } from "@/lib/translations";
import { useSettingsStore } from "@/stores/useSettingsStore";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ErrorBoundary] Uncaught error:", error, info.componentStack);
  }

  private t(key: string): string {
    const lang = useSettingsStore.getState().language;
    return translate(lang, key);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          padding: "2rem",
          fontFamily: "var(--font-inter), system-ui, sans-serif",
          color: "var(--text, #212121)",
          background: "var(--bg, #f5f5f5)",
        }}>
          <h2 style={{ marginBottom: "0.5rem", fontSize: "1.25rem" }}>
            {this.t("error.title")}
          </h2>
          <p style={{
            marginBottom: "1rem",
            fontSize: "0.875rem",
            color: "var(--text2, #616161)",
            maxWidth: "400px",
            textAlign: "center",
          }}>
            {this.state.error?.message || this.t("error.fallback")}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              padding: "0.5rem 1.25rem",
              borderRadius: "0.5rem",
              border: "1px solid var(--overlay, #e0e0e0)",
              background: "var(--surface, #ffffff)",
              color: "var(--text, #212121)",
              cursor: "pointer",
              fontSize: "0.875rem",
            }}
          >
            {this.t("error.retry")}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
