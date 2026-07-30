import { useEffect, useReducer, useRef, useState } from "react";
import { initialTapState, tapReducer, TAP_WINDOW_MS } from "./tapWindow";

export function useTapWindow(onPublish: (taps: number) => void) {
  const [state, dispatch] = useReducer(tapReducer, initialTapState);
  const [msLeft, setMsLeft] = useState(0);
  const fired = useRef(false);

  useEffect(() => {
    if (state.deadline === null || state.published) return;
    const iv = setInterval(() => {
      const now = Date.now();
      setMsLeft(Math.max(0, state.deadline! - now));
      dispatch({ type: "expire", now });
    }, 50);
    return () => clearInterval(iv);
  }, [state.deadline, state.published]);

  useEffect(() => {
    if (state.published && !fired.current) {
      fired.current = true;
      onPublish(state.count);
    }
    if (!state.published) fired.current = false;
  }, [state.published, state.count, onPublish]);

  return {
    count: state.count,
    active: state.deadline !== null && !state.published,
    msLeft,
    windowMs: TAP_WINDOW_MS,
    tap: () => {
      if (navigator.vibrate) navigator.vibrate(30);
      dispatch({ type: "tap", now: Date.now() });
    },
    cancel: () => dispatch({ type: "cancel" }),
  };
}
