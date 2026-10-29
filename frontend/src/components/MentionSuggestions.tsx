import type { RefObject } from "react";
import { useQuery } from "@tanstack/react-query";
import { Popover as PopoverPrimitive } from "@base-ui/react/popover";
import { api } from "@/lib/api";
import { activeMention, insertMention } from "@/lib/mentions";
import { useDebounced } from "@/lib/useDebounced";
import { Popover } from "@/components/ui/popover";
import UserLink from "@/components/UserLink";
import type { Author } from "@/lib/types";

/** @-autocomplete above a composer field. Never takes focus: on a phone,
 *  moving focus closes the keyboard mid-word.
 *
 *  ui/popover's PopoverContent does not forward `anchor` (a Positioner prop)
 *  nor keep focus out of the Popup, so the base-ui parts are composed here with
 *  the same surface classes. ui/popover.tsx itself is untouched. */
export default function MentionSuggestions({
  value,
  caret,
  anchor,
  onPick,
}: {
  value: string;
  caret: number;
  anchor: RefObject<HTMLElement | null>;
  onPick: (next: { value: string; caret: number }) => void;
}) {
  const active = activeMention(value, caret);
  const query = useDebounced(active?.query ?? "", 200);
  const q = useQuery({
    queryKey: ["user-search", query],
    queryFn: () =>
      api<{ users: Author[] }>(`/api/users/search?q=${encodeURIComponent(query)}`),
    enabled: query.length > 0,
    staleTime: 30_000,
  });
  const users = active && query === active.query ? (q.data?.users ?? []) : [];
  return (
    <Popover open={users.length > 0} modal={false}>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Positioner
          anchor={anchor}
          side="top"
          align="start"
          sideOffset={4}
          className="isolate z-50"
        >
          <PopoverPrimitive.Popup
            data-slot="popover-content"
            initialFocus={false}
            finalFocus={false}
            className="z-50 w-64 origin-(--transform-origin) rounded-none bg-popover p-1 text-sm text-popover-foreground shadow-md ring-1 ring-foreground/10 outline-hidden"
          >
            <ul>
              {users.map((u) => (
                <li key={u.id}>
                  <button
                    type="button"
                    // Pointer/mouse down are only cancelled, to keep focus (and
                    // the keyboard) on the field. The pick runs on click: picking
                    // on pointerdown changes `value`, unmounts this list before
                    // the finger lifts, and the browser's follow-up click would
                    // land on whatever is underneath (a ghost tap).
                    onPointerDown={(e) => e.preventDefault()}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() =>
                      onPick(insertMention(value, active!.start, caret, u.username!))
                    }
                    className="flex w-full items-center gap-2 px-2 py-2 text-left text-sm"
                  >
                    <UserLink user={u} avatar size={24} plain />
                    <UserLink user={u} plain />
                    <span className="truncate text-muted-foreground">{u.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          </PopoverPrimitive.Popup>
        </PopoverPrimitive.Positioner>
      </PopoverPrimitive.Portal>
    </Popover>
  );
}
