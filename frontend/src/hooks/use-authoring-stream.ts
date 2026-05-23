"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { StreamEvent, StreamState, StreamStatus } from "@/core/cer_auth/stream_types";

const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_RECONNECT_DELAY_MS = 1000;

function getBackendBaseURL(): string {
  if (typeof window === "undefined") return "";
  return process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "";
}

export function useAuthoringStream(threadId: string | null) {
  const [state, setState] = useState<StreamState>({
    events: [],
    status: "idle",
    error: null,
    currentNode: null,
    interruptPayload: null,
    gateResults: [],
    quickScanResults: [],
  });

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (!threadId) return;

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    setState((prev) => ({
      ...prev,
      status: "connecting",
      error: null,
    }));

    const base = getBackendBaseURL();
    const url = `${base}/api/cer-authoring/stream/${encodeURIComponent(threadId)}`;

    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => {
      reconnectAttemptsRef.current = 0;
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as StreamEvent;
        setState((prev) => {
          const nextEvents = [...prev.events, data];
          let nextStatus: StreamStatus = prev.status;
          let currentNode = prev.currentNode;
          let interruptPayload = prev.interruptPayload;
          const gateResults = [...prev.gateResults];
          const quickScanResults = [...prev.quickScanResults];

          switch (data.event) {
            case "node_start":
              nextStatus = "streaming";
              currentNode = data.node;
              break;
            case "node_end":
              currentNode = null;
              break;
            case "interrupt":
              nextStatus = "interrupted";
              interruptPayload = data.payload;
              break;
            case "gate_result":
              gateResults.push(data);
              break;
            case "quick_scan":
              quickScanResults.push(data);
              break;
            case "done":
              nextStatus = "done";
              currentNode = null;
              interruptPayload = null;
              break;
            case "error":
              nextStatus = "error";
              break;
          }

          return {
            ...prev,
            events: nextEvents,
            status: nextStatus,
            currentNode,
            interruptPayload,
            gateResults,
            quickScanResults,
          };
        });
      } catch (err) {
        console.warn("Failed to parse SSE event:", event.data, err);
      }
    };

    es.onerror = () => {
      es.close();
      eventSourceRef.current = null;

      setState((prev) => ({
        ...prev,
        status: "error",
        error: new Error("SSE connection error"),
      }));

      // Auto-reconnect with exponential backoff
      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        const delay =
          BASE_RECONNECT_DELAY_MS * Math.pow(2, reconnectAttemptsRef.current);
        reconnectAttemptsRef.current += 1;
        reconnectTimerRef.current = setTimeout(() => {
          connect();
        }, delay);
      }
    };
  }, [threadId]);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    reconnectAttemptsRef.current = 0;
  }, []);

  useEffect(() => {
    if (threadId) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [threadId, connect, disconnect]);

  return {
    ...state,
    connect,
    disconnect,
  };
}
