import { useCallback } from 'react';
import { useRunDataStore } from '../store/runData';
import type { RunData } from '../types/runData';

export function useRunData() {
  const { runData, isSampleData, setRunData, loadSampleData } = useRunDataStore();

  const loadFile = useCallback((file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const json = JSON.parse(e.target?.result as string) as RunData;
        setRunData(json, false);
      } catch (err) {
        console.error('Failed to parse run.json:', err);
        alert('Invalid run.json file. Please check the format.');
      }
    };
    reader.readAsText(file);
  }, [setRunData]);

  return { runData, isSampleData, loadFile, loadSampleData };
}
