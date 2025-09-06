import React from 'react';
import { Alert, ScrollArea } from '@mantine/core';

interface State { hasError: boolean; error?: unknown }

export class ErrorBoundary extends React.Component<React.PropsWithChildren, State> {
  state: State = { hasError: false };
  static getDerivedStateFromError(error: unknown) { return { hasError: true, error }; }
  componentDidCatch(error: unknown, info: unknown) { console.error('UI ErrorBoundary', error, info); }
  render() {
    if (this.state.hasError) {
      return (
        <ScrollArea style={{ maxHeight: '100vh' }}>
          <Alert color="red" title="UI Error" variant="filled">
            <pre style={{ whiteSpace:'pre-wrap', fontSize:12 }}>{String(this.state.error)}</pre>
          </Alert>
        </ScrollArea>
      );
    }
    return this.props.children;
  }
}
