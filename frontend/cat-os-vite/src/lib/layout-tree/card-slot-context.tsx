import { createContext, useContext } from "react";
import type { CardId } from "@/state/layoutStore";

export interface CardSlotContextValue {
  leafId: string;
  cardId: CardId;
  replaceCard: (newCardId: CardId) => void;
}

export const CardSlotContext = createContext<CardSlotContextValue | null>(null);

export function useCardSlot() {
  return useContext(CardSlotContext);
}
