import { create } from 'zustand';
import type { RunData, TraceRow } from '../types/runData';

interface RunDataState {
  runData: RunData | null;
  isSampleData: boolean;
  selectedRow: TraceRow | null;
  pipelineAnimating: boolean;
  setRunData: (data: RunData, isSample?: boolean) => void;
  setSelectedRow: (row: TraceRow | null) => void;
  setPipelineAnimating: (val: boolean) => void;
  loadSampleData: () => void;
}

export const useRunDataStore = create<RunDataState>((set) => ({
  runData: null,
  isSampleData: false,
  selectedRow: null,
  pipelineAnimating: false,
  setRunData: (data, isSample = false) => set({ runData: data, isSampleData: isSample, selectedRow: null }),
  setSelectedRow: (row) => set({ selectedRow: row, pipelineAnimating: true }),
  setPipelineAnimating: (val) => set({ pipelineAnimating: val }),
  loadSampleData: () => set({ runData: null, isSampleData: false, selectedRow: null }),
}));
