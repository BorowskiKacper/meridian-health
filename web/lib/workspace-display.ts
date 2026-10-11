/** Wait for the requested content to reach a visible browser frame. */
export function waitForWorkspaceDisplay(tabId: string | null, jobId: string, timeout = 500): Promise<boolean> {
  if (document.visibilityState !== 'visible') return Promise.resolve(false);
  return new Promise((resolve) => {
    let frame = 0;
    let visibleFrames = 0;
    const finish = (displayed: boolean) => { clearTimeout(timer); cancelAnimationFrame(frame); resolve(displayed); };
    const timer = setTimeout(() => finish(false), timeout);
    const check = () => {
      const elements = document.querySelectorAll<HTMLElement>(tabId ? '[data-workspace-tab]' : '[data-workspace-reply]');
      const content = [...elements].find((el) => tabId ? el.dataset.workspaceTab === tabId && el.dataset.workspaceReady === 'true' : el.dataset.workspaceReply === jobId);
      const visible = document.visibilityState === 'visible' && content && content.getClientRects().length > 0;
      visibleFrames = visible ? visibleFrames + 1 : 0;
      if (visibleFrames >= 2) finish(true);
      else frame = requestAnimationFrame(check);
    };
    frame = requestAnimationFrame(check);
  });
}
