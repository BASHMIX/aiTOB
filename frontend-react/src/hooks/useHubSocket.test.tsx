import { renderHook, act } from '@testing-library/react';

import { useHubSocket } from './useHubSocket';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

const PORT = 8000;
const URL = `ws://localhost:${PORT}/ws/hub`;

describe('useHubSocket', () => {
  let mockWebSocketInstance: any;

  beforeEach(() => {
    Object.defineProperty(window, 'location', {
      value: {
        protocol: 'http:',
        host: `localhost:${PORT}`
      },
      writable: true
    });

    mockWebSocketInstance = {
      close: vi.fn(),
      addEventListener: vi.fn(),
      readyState: 0 // CONNECTING
    };

    // Mock global WebSocket using a class so `new WebSocket()` works
    class MockWebSocket {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;

      constructor(url: string) {
        // Log construction to allow expect(MockWebSocket).toHaveBeenCalledWith
        if ((MockWebSocket as any).spy) {
          (MockWebSocket as any).spy(url);
        }
        return mockWebSocketInstance;
      }
    }

    (MockWebSocket as any).spy = vi.fn();

    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('should connect to the websocket and receive messages', () => {
    const onEvent = vi.fn();
    renderHook(() => useHubSocket(onEvent));

    expect((window.WebSocket as any).spy).toHaveBeenCalledWith(URL);

    // Simulate open
    mockWebSocketInstance.readyState = WebSocket.OPEN;
    if (mockWebSocketInstance.onopen) {
      mockWebSocketInstance.onopen();
    }

    const mockEvent = { type: 'match_update', id: 1 };

    // Simulate message
    act(() => {
      if (mockWebSocketInstance.onmessage) {
        mockWebSocketInstance.onmessage({ data: JSON.stringify(mockEvent) });
      }
    });

    expect(onEvent).toHaveBeenCalledWith(mockEvent);
  });

  it('should handle malformed JSON messages gracefully', () => {
    const onEvent = vi.fn();
    renderHook(() => useHubSocket(onEvent));

    // Simulate open
    mockWebSocketInstance.readyState = WebSocket.OPEN;
    if (mockWebSocketInstance.onopen) {
      mockWebSocketInstance.onopen();
    }

    // Simulate invalid message
    act(() => {
      if (mockWebSocketInstance.onmessage) {
        mockWebSocketInstance.onmessage({ data: 'invalid json' });
      }
    });

    expect(onEvent).not.toHaveBeenCalled();
  });

  it('should attempt to reconnect when the socket closes', () => {
    const onEvent = vi.fn();
    renderHook(() => useHubSocket(onEvent));

    // Initially called once
    expect((window.WebSocket as any).spy).toHaveBeenCalledTimes(1);

    // Simulate close
    act(() => {
      if (mockWebSocketInstance.onclose) {
        mockWebSocketInstance.onclose();
      }
    });

    // Fast-forward reconnect timer
    act(() => {
      vi.advanceTimersByTime(3000);
    });

    // Should have created a new connection
    expect((window.WebSocket as any).spy).toHaveBeenCalledTimes(2);
  });

  it('should attempt to reconnect on socket error', () => {
    const onEvent = vi.fn();
    renderHook(() => useHubSocket(onEvent));

    // Simulate error
    act(() => {
      if (mockWebSocketInstance.onerror) {
        mockWebSocketInstance.onerror();
      }
    });

    // The component calls close() on error, which we then expect to trigger onclose logic
    expect(mockWebSocketInstance.close).toHaveBeenCalled();
  });

  it('should clean up and close the socket on unmount when OPEN', () => {
    const onEvent = vi.fn();
    const { unmount } = renderHook(() => useHubSocket(onEvent));

    mockWebSocketInstance.readyState = WebSocket.OPEN;

    unmount();

    expect(mockWebSocketInstance.close).toHaveBeenCalled();
    expect(mockWebSocketInstance.onopen).toBeNull();
    expect(mockWebSocketInstance.onmessage).toBeNull();
    expect(mockWebSocketInstance.onclose).toBeNull();
    expect(mockWebSocketInstance.onerror).toBeNull();
  });

  it('should schedule close on unmount when CONNECTING', () => {
    const onEvent = vi.fn();
    const { unmount } = renderHook(() => useHubSocket(onEvent));

    mockWebSocketInstance.readyState = WebSocket.CONNECTING;

    unmount();

    expect(mockWebSocketInstance.addEventListener).toHaveBeenCalledWith('open', expect.any(Function), { once: true });

    // Simulate the 'open' event that should trigger the scheduled close
    const addEventListenerCall = mockWebSocketInstance.addEventListener.mock.calls.find(
      (call: any[]) => call[0] === 'open'
    );

    expect(addEventListenerCall).toBeDefined();
    if (addEventListenerCall) {
      const openCallback = addEventListenerCall[1];
      openCallback();
      expect(mockWebSocketInstance.close).toHaveBeenCalled();
    }
  });
});
