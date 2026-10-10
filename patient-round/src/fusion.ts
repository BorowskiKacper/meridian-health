import {
  NOW_MINUTE,
  fibulaProposal,
  findingVisible,
  findings as openingFindings,
  patient,
  severityLabel,
  type Finding,
  type Specialty,
} from './case.ts';

export type RouteName = 'chart' | 'research' | 'screening';
export type SuggestionStatus = 'pending' | 'approved' | 'rejected';

export interface Suggestion {
  id: string;
  route: RouteName;
  status: SuggestionStatus;
  title: string;
  before: string;
  after: string;
  source: string;
  confidence: string;
  citation: string;
  finding?: Finding;
  reminder?: string;
  noteFor?: string;
  noteText?: string;
}

export interface ChatTurn {
  role: 'doctor' | 'desk';
  text: string;
}

type Handlers = {
  onVisible: () => void;
  onFocus: (finding: Finding) => void;
};

const routeLabel: Record<RouteName, string> = {
  chart: 'Chart-update agent',
  research: 'Research agent',
  screening: 'Screening agent',
};

let seq = 1;

function nextId(prefix: string): string {
  seq += 1;
  return `${prefix}-${seq}`;
}

export class Fusion {
  minute = NOW_MINUTE;
  specialty: Specialty = 'trauma';
  approved: Finding[] = openingFindings.map((finding) => ({ ...finding }));
  reminders: string[] = [];
  suggestions: Suggestion[] = [
    {
      id: 'sug-fibula',
      route: 'chart',
      status: 'pending',
      title: 'Watch the left fibula',
      before: 'Left fibula is not on the chart.',
      after: 'Watch mark on the left fibula, visible on the limb.',
      source: 'Chart-update agent · propose_change',
      confidence: 'Needs a doctor',
      citation: 'Bedside exam this visit. Not a guideline search.',
      finding: { ...fibulaProposal },
    },
  ];
  chat: ChatTurn[] = [
    {
      role: 'desk',
      text: 'One typed box, same as the routing graph. A request is classified as a chart update, a clinical question, or a screening check. Nothing here writes the chart. Approving a suggestion is the only path that changes the body.',
    },
  ];
  activeId = openingFindings[0]!.id;
  private handlers: Handlers = { onVisible: () => {}, onFocus: () => {} };

  bind(handlers: Handlers): void {
    this.handlers = handlers;
    document.querySelector<HTMLElement>('#patient-name')!.textContent = patient.name;
    document.querySelector<HTMLElement>('#patient-meta')!.textContent = patient.meta;
    document.querySelector<HTMLElement>('#patient-story')!.textContent = patient.story;

    document.querySelectorAll<HTMLButtonElement>('[data-desk]').forEach((button) => {
      button.addEventListener('click', () => this.showDesk(button.dataset.desk || 'body'));
    });

    const specialty = document.querySelector<HTMLSelectElement>('#specialty')!;
    specialty.addEventListener('change', () => {
      this.specialty = specialty.value as Specialty;
      const visible = this.visible();
      if (!visible.some((finding) => finding.id === this.activeId)) {
        this.activeId = visible[visible.length - 1]?.id ?? '';
      }
      this.handlers.onVisible();
      this.render();
    });

    const timeline = document.querySelector<HTMLInputElement>('#timeline')!;
    timeline.max = String(NOW_MINUTE);
    timeline.value = String(this.minute);
    timeline.addEventListener('input', () => {
      this.minute = Number(timeline.value);
      const visible = this.visible();
      if (!visible.some((finding) => finding.id === this.activeId)) {
        this.activeId = visible[visible.length - 1]?.id ?? '';
      }
      this.handlers.onVisible();
      this.render();
    });

    document.querySelector<HTMLFormElement>('#chat')!.addEventListener('submit', (event) => {
      event.preventDefault();
      const input = document.querySelector<HTMLInputElement>('#chat-input')!;
      const text = input.value.trim();
      if (!text) return;
      input.value = '';
      this.ask(text);
    });

    document.querySelector<HTMLOListElement>('#queue')!.addEventListener('click', (event) => {
      const button = (event.target as HTMLElement).closest<HTMLButtonElement>('[data-decision]');
      if (!button) return;
      const id = button.dataset.id;
      if (!id) return;
      if (button.dataset.decision === 'approve') this.approve(id);
      else this.reject(id);
    });

    document.querySelector<HTMLElement>('#region-detail')!.addEventListener('click', (event) => {
      const button = (event.target as HTMLElement).closest<HTMLButtonElement>('[data-plan]');
      if (!button?.dataset.plan) return;
      this.addPlan(button.dataset.plan);
    });

    this.render();
  }

  visible(): Finding[] {
    return this.approved.filter((finding) => findingVisible(finding, this.minute, this.specialty));
  }

  active(): Finding | undefined {
    return this.visible().find((finding) => finding.id === this.activeId) ?? this.visible().at(-1);
  }

  showDesk(name: string): void {
    document.querySelectorAll<HTMLButtonElement>('[data-desk]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.desk === name));
    });
    document.querySelectorAll<HTMLElement>('[data-panel]').forEach((panel) => {
      panel.hidden = panel.dataset.panel !== name;
    });
  }

  render(latinOf?: (id: string) => string | undefined): void {
    this.renderTimeline();
    this.renderFindings(latinOf);
    this.renderRegion();
    this.renderChat();
    this.renderQueue();
    const pending = this.suggestions.filter((item) => item.status === 'pending').length;
    const count = document.querySelector<HTMLElement>('#queue-count')!;
    count.textContent = pending ? String(pending) : '';
    count.hidden = pending === 0;
  }

  private renderTimeline(): void {
    const caption = document.querySelector<HTMLElement>('#timeline-caption')!;
    const latest = [...this.approved].reverse().find((finding) => finding.minute <= this.minute);
    caption.textContent = latest
      ? `${this.minute} min · ${latest.title}`
      : `${this.minute} min · arrived, nothing charted yet`;
    const list = document.querySelector<HTMLOListElement>('#timeline-events')!;
    list.replaceChildren();
    const arrival = document.createElement('li');
    arrival.textContent = '0 min · Arrived from the kerb';
    arrival.classList.toggle('is-future', this.minute < 0);
    list.append(arrival);
    for (const finding of this.approved) {
      const item = document.createElement('li');
      item.textContent = `${finding.minute} min · ${finding.title}`;
      item.classList.toggle('is-future', finding.minute > this.minute);
      item.classList.toggle('is-dim', !findingVisible(finding, NOW_MINUTE, this.specialty));
      list.append(item);
    }
  }

  private renderFindings(latinOf?: (id: string) => string | undefined): void {
    const list = document.querySelector<HTMLOListElement>('#findings')!;
    list.replaceChildren();
    const visible = this.visible();
    if (!visible.length) {
      const empty = document.createElement('li');
      empty.className = 'empty';
      empty.textContent = 'Nothing on the body for this time and specialty. Later chart entries are still approved — move the timeline forward.';
      list.append(empty);
      return;
    }
    visible.forEach((finding, index) => {
      const item = document.createElement('li');
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `finding ${finding.severity}`;
      button.dataset.finding = finding.id;
      button.innerHTML = `<i></i><span class="kicker"></span><strong></strong><span class="latin"></span><span class="note"></span>`;
      button.querySelector('.kicker')!.textContent = `${String(index + 1).padStart(2, '0')}  ${severityLabel[finding.severity]}`;
      button.querySelector('strong')!.textContent = finding.title;
      button.querySelector('.note')!.textContent = finding.note;
      const latin = latinOf?.(finding.structureId);
      const latinNode = button.querySelector('.latin')!;
      if (latin && latin !== finding.structureId && latin !== finding.title) latinNode.textContent = latin;
      else latinNode.remove();
      button.classList.toggle('is-current', finding.id === this.activeId);
      button.addEventListener('click', () => this.focus(finding));
      item.append(button);
      list.append(item);
    });
  }

  focus(finding: Finding): void {
    this.activeId = finding.id;
    this.showDesk('region');
    this.handlers.onFocus(finding);
    this.render();
  }

  private renderRegion(): void {
    const root = document.querySelector<HTMLElement>('#region-detail')!;
    const finding = this.approved.find((item) => item.id === this.activeId) ?? this.active();
    root.replaceChildren();
    if (!finding) {
      const empty = document.createElement('p');
      empty.className = 'hint';
      empty.textContent = 'No region is on the body at this point in the timeline.';
      root.append(empty);
      return;
    }
    const onBody = this.visible().some((item) => item.id === finding.id);
    const title = document.createElement('h2');
    title.textContent = finding.title;
    const condition = document.createElement('p');
    condition.className = 'condition';
    condition.textContent = finding.condition;
    const note = document.createElement('p');
    note.className = 'story';
    note.textContent = onBody
      ? finding.note
      : `${finding.note} The timeline is before minute ${finding.minute}, so this mark is off the model until you move it forward.`;
    root.append(title, condition, note);
    root.append(labeledList('Medications', finding.meds));
    root.append(labeledList('Observations', finding.observations.map((item) => `${item.label}: ${item.value}`)));
    if (this.reminders.length) root.append(labeledList('Reminders on the chart', this.reminders));
    if (finding.id === 'spleen') {
      const plan = document.createElement('button');
      plan.type = 'button';
      plan.className = 'solid plan';
      plan.dataset.plan = 'spleen-clear';
      plan.textContent = 'Add the clear spleen call to the plan';
      root.append(plan);
    }
  }

  private renderChat(): void {
    const log = document.querySelector<HTMLOListElement>('#chat-log')!;
    log.replaceChildren();
    for (const turn of this.chat) {
      const item = document.createElement('li');
      item.className = turn.role;
      item.textContent = turn.text;
      log.append(item);
    }
    log.scrollTop = log.scrollHeight;
  }

  private renderQueue(): void {
    const list = document.querySelector<HTMLOListElement>('#queue')!;
    list.replaceChildren();
    const ordered = [...this.suggestions].reverse();
    if (!ordered.length) {
      const empty = document.createElement('li');
      empty.className = 'empty';
      empty.textContent = 'No suggestions. Ask in chat to update the chart, ask a question, or check screenings.';
      list.append(empty);
      return;
    }
    for (const suggestion of ordered) {
      const item = document.createElement('li');
      item.className = `card ${suggestion.status}`;
      const kicker = document.createElement('p');
      kicker.className = 'kicker';
      kicker.textContent = `${routeLabel[suggestion.route]} · ${suggestion.status}`;
      const title = document.createElement('strong');
      title.textContent = suggestion.title;
      const diff = document.createElement('p');
      diff.textContent = `Before: ${suggestion.before} After: ${suggestion.after}`;
      const meta = document.createElement('p');
      meta.className = 'hint';
      meta.textContent = `${suggestion.source}. ${suggestion.confidence}. ${suggestion.citation}`;
      item.append(kicker, title, diff, meta);
      if (suggestion.status === 'pending') {
        const actions = document.createElement('div');
        actions.className = 'card-actions';
        actions.append(decisionButton('approve', suggestion.id, 'Approve'), decisionButton('reject', suggestion.id, 'Reject'));
        item.append(actions);
      }
      list.append(item);
    }
  }

  private ask(text: string): void {
    this.chat.push({ role: 'doctor', text });
    const route = classify(text);
    if (route === 'screening') this.proposeScreening(text);
    else if (route === 'chart') this.proposeChart(text);
    else this.answerResearch(text);
    this.showDesk('chat');
    this.render();
  }

  private proposeChart(text: string): void {
    const fibula = /fibula/.test(text.toLowerCase());
    if (fibula && this.approved.some((finding) => finding.id === 'fibula')) {
      this.chat.push({
        role: 'desk',
        text: 'D2 classified this as a chart update. The left fibula is already approved, so nothing new was proposed.',
      });
      return;
    }
    if (fibula) {
      const existing = this.suggestions.find((item) => item.finding?.id === 'fibula' && item.status === 'pending');
      this.chat.push({
        role: 'desk',
        text: existing
          ? 'D2 classified this as a chart update. propose_change already has a pending fibula suggestion. The body stays as it is until you approve it.'
          : 'D2 classified this as a chart update. propose_change queued a fibula mark. The body will not show it until you approve.',
      });
      if (!existing) {
        this.suggestions.push({
          id: nextId('sug'),
          route: 'chart',
          status: 'pending',
          title: 'Watch the left fibula',
          before: 'Left fibula is not on the chart.',
          after: 'Watch mark on the left fibula.',
          source: 'Chart-update agent · propose_change',
          confidence: 'Needs a doctor',
          citation: 'Taken from the typed request. Not written to the chart yet.',
          finding: { ...fibulaProposal, note: text },
        });
      }
      return;
    }
    const target = this.active();
    if (!target) {
      this.chat.push({ role: 'desk', text: 'D2 classified this as a chart update, but no region is active to attach a note to.' });
      return;
    }
    this.suggestions.push({
      id: nextId('sug'),
      route: 'chart',
      status: 'pending',
      title: `Note on ${target.title}`,
      before: target.note,
      after: text,
      source: 'Chart-update agent · propose_change',
      confidence: 'Needs a doctor',
      citation: 'Typed request. A note suggestion does not write until approval.',
      noteFor: target.id,
      noteText: text,
    });
    this.chat.push({
      role: 'desk',
      text: `D2 classified this as a chart update. A note for ${target.title} is in the queue. The mark on the model still shows the approved note.`,
    });
  }

  private answerResearch(text: string): void {
    const spleen = this.approved.find((finding) => finding.id === 'spleen');
    const aboutSpleen = /spleen/i.test(text);
    const subject = aboutSpleen && spleen ? spleen : this.active();
    const citation = aboutSpleen
      ? 'Approved chart at 36 min, plus ATLS: recheck the abdomen if the exam changes. Demo citation, not a live Snowflake search.'
      : 'Answered from the approved chart only. Demo citation, not a live guideline search.';
    const body = subject
      ? `${subject.title}: ${subject.condition}. ${subject.note} ${citation}`
      : `Nothing is on the body at minute ${this.minute}. ${citation}`;
    this.chat.push({
      role: 'desk',
      text: `D2 classified this as a clinical question. The research agent read the chart and did not propose a write. ${body}`,
    });
  }

  private proposeScreening(text: string): void {
    const existing = this.suggestions.find((item) => item.reminder && item.status === 'pending');
    this.chat.push({
      role: 'desk',
      text: existing
        ? 'D2 classified this as a screening check. A colonoscopy reminder is already waiting in the queue.'
        : 'D2 classified this as a screening check. search_guidelines would look up USPSTF here. The demo queued a reminder instead of sending it. Age 47 is already inside the 45-year start.',
    });
    if (!existing) {
      this.suggestions.push({
        id: nextId('sug'),
        route: 'screening',
        status: 'pending',
        title: 'Counsel on colorectal screening',
        before: 'No screening reminder on the chart.',
        after: 'Reminder: colorectal screening is due to discuss. Start age in the guideline is 45.',
        source: 'Screening agent · propose_change',
        confidence: 'Needs a doctor',
        citation: 'USPSTF colorectal cancer screening, average risk from age 45. Demo citation, not a Snowflake call.',
        reminder: `Colorectal screening discussion. Asked as: ${text}`,
      });
    }
  }

  private addPlan(kind: string): void {
    if (kind !== 'spleen-clear') return;
    const existing = this.suggestions.find((item) => item.noteFor === 'spleen' && item.status === 'pending');
    if (!existing) {
      this.suggestions.push({
        id: nextId('sug'),
        route: 'research',
        status: 'pending',
        title: 'Record the clear spleen call',
        before: 'The clear call is a finding note only.',
        after: 'Approved note: spleen reviewed, no free fluid, no blush.',
        source: 'Research agent · add to plan',
        confidence: 'Needs a doctor',
        citation: 'Approved chart at 36 min. Add to plan creates a suggestion, not a chart write.',
        noteFor: 'spleen',
        noteText: 'Reviewed this visit. No free fluid and no blush. Cleared for now.',
      });
    }
    this.chat.push({
      role: 'desk',
      text: 'Add to plan created a suggestion. The spleen mark changes only if you approve it.',
    });
    this.showDesk('queue');
    this.render();
  }

  private approve(id: string): void {
    const suggestion = this.suggestions.find((item) => item.id === id && item.status === 'pending');
    if (!suggestion) return;
    suggestion.status = 'approved';
    let focus: Finding | null = null;
    if (suggestion.finding && !this.approved.some((item) => item.id === suggestion.finding!.id)) {
      this.approved.push(suggestion.finding);
      this.minute = Math.max(this.minute, suggestion.finding.minute);
      const slider = document.querySelector<HTMLInputElement>('#timeline');
      if (slider) slider.value = String(this.minute);
      focus = suggestion.finding;
      this.activeId = suggestion.finding.id;
    }
    if (suggestion.noteFor && suggestion.noteText) {
      const finding = this.approved.find((item) => item.id === suggestion.noteFor);
      if (finding) {
        finding.note = suggestion.noteText;
        focus = finding;
        this.activeId = finding.id;
      }
    }
    if (suggestion.reminder) this.reminders.push(suggestion.reminder);
    this.chat.push({
      role: 'desk',
      text: focus
        ? `Approved. The chart write refreshed the body: ${focus.title} is on the model.`
        : 'Approved. The reminder is on the chart. No structure changed, so the body stays as it was.',
    });
    this.handlers.onVisible();
    if (focus && this.visible().some((item) => item.id === focus!.id)) this.handlers.onFocus(focus);
    this.showDesk(focus ? 'region' : 'queue');
    this.render();
  }

  private reject(id: string): void {
    const suggestion = this.suggestions.find((item) => item.id === id && item.status === 'pending');
    if (!suggestion) return;
    suggestion.status = 'rejected';
    this.chat.push({
      role: 'desk',
      text: `Rejected “${suggestion.title}”. The chart and the body are unchanged.`,
    });
    this.render();
  }
}

function classify(text: string): RouteName {
  const value = text.toLowerCase();
  if (/screen|colonoscopy|reminder|mammogram|prevent|due for/.test(value)) return 'screening';
  if (/\?|why |what |how |is the|should |guideline|concern|cleared|clear/.test(value) && !/^add |^note |^document /.test(value)) {
    return 'research';
  }
  if (/add |note |document |mark |record |update |chart |fibula|watch /.test(value)) return 'chart';
  return 'research';
}

function labeledList(title: string, items: string[]): HTMLElement {
  const wrap = document.createElement('section');
  const heading = document.createElement('h3');
  heading.textContent = title;
  const list = document.createElement('ul');
  for (const item of items) {
    const li = document.createElement('li');
    li.textContent = item;
    list.append(li);
  }
  wrap.append(heading, list);
  return wrap;
}

function decisionButton(decision: 'approve' | 'reject', id: string, label: string): HTMLButtonElement {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = decision === 'approve' ? 'solid' : 'ghost';
  button.dataset.decision = decision;
  button.dataset.id = id;
  button.textContent = label;
  return button;
}
