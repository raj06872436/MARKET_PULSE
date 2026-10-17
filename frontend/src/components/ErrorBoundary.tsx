import { Component, type ErrorInfo, type ReactNode } from "react";

/** Keeps one broken page from blanking the whole app; the navigation stays usable. */
export class ErrorBoundary extends Component<{ children: ReactNode; resetKey: string }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Page crashed", error, info.componentStack);
  }

  componentDidUpdate(prev: { resetKey: string }) {
    if (prev.resetKey !== this.props.resetKey && this.state.failed) this.setState({ failed: false });
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className="rounded-lg border border-red-200 bg-white p-6 text-sm">
        <p className="font-medium text-red-800">This page hit an error.</p>
        <p className="mt-1 text-slate-600">Your data is safe. Reload the page, or pick another page from the menu.</p>
        <button onClick={() => window.location.reload()}
          className="mt-3 rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-50">Reload</button>
      </div>
    );
  }
}
