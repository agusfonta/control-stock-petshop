import { create } from "zustand";

interface HealthState {
  version: string | null;
  setVersion: (version: string) => void;
}

export const useHealthStore = create<HealthState>()((set) => ({
  version: null,
  setVersion: (version: string) => set({ version }),
}));
