import { useCallback, useEffect, useRef, useState } from 'react';
import { researchApi, ResearchApiError } from '@/adapters/research-api-adapter';
import type { ResearchVersion, ResearchCatalog, ResearchRunStatus } from '@/adapters/research-api-adapter';

function detail(error: unknown): string {
  return error instanceof ResearchApiError ? `[${error.status}]: ${error.detail}` : '連線或資料讀取失敗';
}

type Send<Req> = (request: Req, buildId: string, signal?: AbortSignal) => Promise<ResearchRunStatus>;

/**
 * Runs of one research kind: list, shared busy-slot polling, archived result loading and submission.
 * `label` names the kind in error messages (e.g. 優化, 驗證).
 */
export function useResearchRuns<Req, Res>(kind: ResearchRunStatus['kind'], label: string, send: Send<Req>) {
  const [version, setVersion] = useState<ResearchVersion | null>(null);
  const [catalog, setCatalog] = useState<ResearchCatalog | null>(null);
  const [runs, setRuns] = useState<ResearchRunStatus[]>([]);
  const [selectedRun, setSelectedRun] = useState<ResearchRunStatus | null>(null);
  const [realResult, setRealResult] = useState<Res | null>(null);
  const [loading, setLoading] = useState(false);
  const [resultLoading, setResultLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [resultGeneration, setResultGeneration] = useState(0);
  const mounted = useRef(false);
  const snapshotGeneration = useRef(0);
  const refreshRequest = useRef<AbortController | null>(null);
  const submitRequest = useRef<AbortController | null>(null);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      snapshotGeneration.current++;
      refreshRequest.current?.abort();
      submitRequest.current?.abort();
    };
  }, []);

  const applySnapshot = useCallback((ver: ResearchVersion, all: ResearchRunStatus[]) => {
    const filtered = all.filter((run) => run.kind === kind);
    setVersion(ver);
    setRuns(filtered);
    // Completion must never take the selection away from another historical run.
    setSelectedRun((current) => current
      ? filtered.find((run) => run.run_id === current.run_id) ?? current
      : filtered[0] ?? null);
  }, [kind]);

  const fetchRealData = useCallback(async () => {
    refreshRequest.current?.abort();
    const request = new AbortController();
    refreshRequest.current = request;
    const generation = ++snapshotGeneration.current;
    setLoading(true);
    setErrorMsg(null);
    try {
      const [ver, cat, all] = await Promise.all([
        researchApi.getVersion(request.signal), researchApi.getCatalog(request.signal), researchApi.getRuns(request.signal),
      ]);
      if (!mounted.current || request.signal.aborted || generation !== snapshotGeneration.current) return;
      setCatalog(cat);
      applySnapshot(ver, all);
    } catch (error) {
      if (mounted.current && !request.signal.aborted && generation === snapshotGeneration.current) {
        setErrorMsg(`讀取研究狀態失敗 ${detail(error)}`);
      }
    } finally {
      if (mounted.current && refreshRequest.current === request) setLoading(false);
    }
  }, [applySnapshot]);

  useEffect(() => { void fetchRealData(); }, [fetchRealData]);

  const activeRunId = version?.active_run_id ?? null;
  useEffect(() => {
    if (!activeRunId) return;
    const request = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const step = async () => {
      const generation = ++snapshotGeneration.current;
      let delay = 600;
      try {
        // Track the shared slot even if it belongs to another research kind.
        const [ver, all] = await Promise.all([
          researchApi.getVersion(request.signal), researchApi.getRuns(request.signal),
        ]);
        if (request.signal.aborted || !mounted.current) return;
        if (generation === snapshotGeneration.current) applySnapshot(ver, all);
      } catch (error) {
        if (request.signal.aborted || !mounted.current) return;
        if (generation === snapshotGeneration.current) {
          setErrorMsg(`研究狀態暫不可用，保留忙碌狀態 ${detail(error)}`);
        }
        delay = 2000;
      }
      if (!request.signal.aborted && mounted.current) timer = setTimeout(step, delay);
    };
    void step();
    return () => { request.abort(); clearTimeout(timer); };
  }, [activeRunId, applySnapshot]);

  const selectRun = useCallback((run: ResearchRunStatus) => {
    setResultGeneration((current) => current + 1);
    setRealResult(null);
    setResultLoading(run.status === 'complete');
    setErrorMsg(null);
    setSelectedRun(run);
  }, []);

  const selectedId = selectedRun?.run_id;
  const selectedStatus = selectedRun?.status;
  const selectedError = selectedRun?.error;
  useEffect(() => {
    const request = new AbortController();
    setRealResult(null);
    setResultLoading(false);
    if (!selectedId || selectedStatus !== 'complete') {
      if (selectedStatus === 'failed') setErrorMsg(`${label}任務 ${selectedId} 執行失敗: ${selectedError ?? '未知原因'}`);
      return () => request.abort();
    }
    setResultLoading(true);
    void researchApi.getRunResult<Res>(selectedId, request.signal)
      .then((result) => {
        if (!request.signal.aborted && mounted.current) setRealResult(result);
      })
      .catch((error: unknown) => {
        if (!request.signal.aborted && mounted.current) setErrorMsg(`讀取${label}結果失敗 ${detail(error)}`);
      })
      .finally(() => {
        if (!request.signal.aborted && mounted.current) setResultLoading(false);
      });
    return () => request.abort();
  }, [selectedId, selectedStatus, selectedError, resultGeneration, label]);

  const submit = async (input: Req): Promise<boolean> => {
    if (!version || version.restart_required || version.active_run_id || submitRequest.current) return false;
    const request = new AbortController();
    submitRequest.current = request;
    setSubmitting(true);
    setErrorMsg(null);
    try {
      const run = await send(input, version.build_id, request.signal);
      if (!mounted.current || request.signal.aborted) return false;
      // Retain busy until a fresh backend version confirms the slot was released.
      snapshotGeneration.current++;
      refreshRequest.current?.abort();
      setVersion((current) => current && { ...current, active_run_id: run.run_id });
      setRuns((current) => [run, ...current.filter((item) => item.run_id !== run.run_id)]);
      selectRun(run);
      return true;
    } catch (error) {
      if (mounted.current && !request.signal.aborted) {
        setErrorMsg(`提交${label}失敗 ${detail(error)}；請刷新任務清單確認，勿盲目重送`);
      }
      return false;
    } finally {
      submitRequest.current = null;
      if (mounted.current) setSubmitting(false);
    }
  };

  return { version, catalog, runs, selectedRun, realResult, loading, resultLoading, submitting,
    errorMsg, fetchRealData, selectRun, submit, isBusy: submitting || activeRunId !== null };
}
