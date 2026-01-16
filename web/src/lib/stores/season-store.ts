import { create } from "zustand";

interface SeasonState {
	selectedSeason: string | null;
	setSelectedSeason: (season: string) => void;
}

export const useSeasonStore = create<SeasonState>((set) => ({
	selectedSeason: null,
	setSelectedSeason: (season) => set({ selectedSeason: season }),
}));
