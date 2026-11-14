import { create } from 'zustand';
import type { RunData, TraceRow } from '../types/runData';

interface RunDataState {
  runData: RunData | null;
  selectedRow: TraceRow | null;
  pipelineAnimating: boolean;
  setRunData: (data: RunData) => void;
  setSelectedRow: (row: TraceRow | null) => void;
  setPipelineAnimating: (val: boolean) => void;
}

export const useRunDataStore = create<RunDataState>((set) => ({
  runData: null,
  selectedRow: null,
  pipelineAnimating: false,
  setRunData: (data) => set({ runData: data, selectedRow: null }),
  setSelectedRow: (row) => set({ selectedRow: row, pipelineAnimating: true }),
  setPipelineAnimating: (val) => set({ pipelineAnimating: val }),
}));
