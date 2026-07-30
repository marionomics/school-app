export const TAP_WINDOW_MS = 1500;

export interface TapState {
  count: number; // 0..3
  deadline: number | null; // epoch ms when the window closes
  published: boolean;
}

export type TapEvent =
  | { type: "tap"; now: number }
  | { type: "expire"; now: number }
  | { type: "cancel" };

export const initialTapState: TapState = { count: 0, deadline: null, published: false };

export function tapReducer(state: TapState, event: TapEvent): TapState {
  if (state.published) return state;
  switch (event.type) {
    case "tap":
      return {
        count: Math.min(3, state.count + 1),
        deadline: event.now + TAP_WINDOW_MS,
        published: false,
      };
    case "expire":
      if (state.deadline !== null && event.now >= state.deadline) {
        return { ...state, published: true };
      }
      return state;
    case "cancel":
      return initialTapState;
  }
}
