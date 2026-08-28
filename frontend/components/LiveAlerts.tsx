"use client";

import { useEffect, useRef, useState } from "react";
import { wsUrl } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import { Card, CardHeader } from "./ui";

type Alert = {
  type: string;
  at: string;
  [k: string]: unknown;
};

/**
 * WebSocket is a push channel on top of REST. On (re)connect we show a hint and
 * rely on the page's REST fetch for the source-of-truth state.
 */
export function LiveAlerts() {
  const [status, setStatus] = useState<"connecting" | "live" | "offline">("connecting");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const retry = useRef(0);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;

    function connect() {
      setStatus("connecting");
      ws = new WebSocket(wsUrl("/ws/alerts"));
      ws.onopen = () => {
        retry.current = 0;
        setStatus("live");
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data) as Alert;
          if (msg.type === "connected" || msg.type === "pong") return;
          setAlerts((a) => [msg, ...a].slice(0, 12));
        } catch {
          /* ignore */
        }
      };
      ws.onclose = () => {
        if (stop) return;
        setStatus("offline");
        retry.current += 1;
        timer = setTimeout(connect, Math.min(15000, 1000 * 2 ** retry.current));
      };
      ws.onerror = () => ws?.close();
    }
    connect();

    const ping = setInterval(() => ws?.readyState === 1 && ws.send("ping"), 25000);
    return () => {
      stop = true;
      clearInterval(ping);
      clearTimeout(timer);
      ws?.close();
    };
  }, []);

  return (
    <Card>
      <CardHeader
        title="Live alerts"
        right={
          <span className="chip">
            <span
              className={
                "h-1.5 w-1.5 rounded-full " +
                (status === "live"
                  ? "animate-pulse-dot bg-emerald-400"
                  : status === "connecting"
                    ? "bg-amber-400"
                    : "bg-slate-500")
              }
            />
            {status}
          </span>
        }
      />
      {alerts.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-600">
          Watching your stations. Threshold crossings and risk-score changes appear here.
        </p>
      ) : (
        <ul className="space-y-2">
          {alerts.map((a, i) => (
            <li
              key={i}
              className="flex items-start gap-3 rounded-lg border border-white/5 bg-white/[0.02] p-3 text-sm animate-fade-up"
            >
              {a.type === "threshold_alert" ? (
                <>
                  <span className="mt-0.5 text-aq-bad">▲</span>
                  <div>
                    <p className="text-slate-200">
                      PM2.5 <b>{String(a.value)}</b> µg/m³ at {String(a.station)} — over the WHO
                      guideline of {String(a.who_guideline)}.
                    </p>
                    <p className="text-[11px] text-slate-500">{timeAgo(a.at)}</p>
                  </div>
                </>
              ) : (
                <>
                  <span className="mt-0.5 text-brand">◆</span>
                  <div>
                    <p className="text-slate-200">
                      Risk score updated to <b>{String(a.risk_score)}</b>/10 (
                      {a.is_personalized ? "personalized" : "population"} model).
                    </p>
                    <p className="text-[11px] text-slate-500">{timeAgo(a.at)}</p>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
