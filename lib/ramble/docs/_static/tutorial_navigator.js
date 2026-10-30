// Copyright 2022-2026 The Ramble Authors
//
// Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
// https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
// <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
// option. This file may not be copied, modified, or distributed
// except according to those terms.

(function () {
  'use strict';

  const STORAGE_KEY = 'ramble_completed_tutorials';
  const GOALS_STORAGE_KEY = 'ramble_selected_goals';
  const APP_STORAGE_KEY = 'ramble_selected_app';
  const DEFAULT_APP = 'wrf';
  const WS_NAME_STORAGE_PREFIX = 'ramble_workspace_name_';
  const GLOBAL_WS_NAME_KEY = 'ramble_tutorial_custom_ws_name';
  const DRY_RUN_STORAGE_KEY = 'ramble_tutorial_dry_run';
  const MODE_STORAGE_KEY = 'ramble_tutorial_mode';
  const THEME_STORAGE_KEY = 'ramble_docs_theme';

  const storage = {
    get(k, fb = null) {
      try { return localStorage.getItem(k) ?? fb; } catch (e) { return fb; }
    },
    set(k, v) {
      try { localStorage.setItem(k, v); } catch (e) { console.warn(`Could not save ${k}:`, e); }
    },
    remove(k) {
      try { localStorage.removeItem(k); } catch (e) { /* ignore */ }
    },
    getJSON(k, fb = null) {
      const raw = this.get(k);
      if (raw === null) return fb;
      try { return JSON.parse(raw); } catch (e) { return fb; }
    },
    setJSON(k, v) {
      this.set(k, JSON.stringify(v));
    },
  };

  function getEffectiveTheme() {
    const stored = storage.get(THEME_STORAGE_KEY);
    if (stored === 'dark' || stored === 'light') return stored;
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(theme) {
    const clean = theme === 'dark' ? 'dark' : 'light';
    document.documentElement?.setAttribute('data-theme', clean);
    document.body?.setAttribute('data-theme', clean);
    const isDark = clean === 'dark';
    document.querySelectorAll('.tn-theme-toggle-btn').forEach((btn) => {
      btn.textContent = isDark ? '☀️ Light Mode' : '🌙 Dark Mode';
      btn.setAttribute('aria-pressed', String(isDark));
    });
  }

  function setTheme(theme) {
    const clean = theme === 'dark' ? 'dark' : 'light';
    storage.set(THEME_STORAGE_KEY, clean);
    applyTheme(clean);
  }

  function initTheme() {
    const aside = document.querySelector('.wy-breadcrumbs li.wy-breadcrumbs-aside');
    if (aside && !aside.querySelector('.tn-theme-toggle-btn')) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'tn-btn tn-btn-sm tn-theme-toggle-btn';
      btn.title = 'Toggle dark/light theme';
      btn.setAttribute('aria-label', 'Toggle dark/light theme');
      aside.insertBefore(btn, aside.firstChild);
    }

    applyTheme(getEffectiveTheme());
  }

  applyTheme(getEffectiveTheme());
  window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', () => {
    if (!storage.get(THEME_STORAGE_KEY)) applyTheme(getEffectiveTheme());
  });

  function bindKeyActivate(el, getTarget) {
    if (!el) return;
    el.addEventListener('keydown', (e) => {
      if (e.key === ' ' || e.key === 'Enter') {
        const target = getTarget ? getTarget(e) : el;
        if (target) {
          e.preventDefault();
          target.click();
        }
      }
    });
  }

  const getStoredSelectedApp = () => storage.get(APP_STORAGE_KEY, DEFAULT_APP) || DEFAULT_APP;
  const getStoredDryRun = () => storage.get(DRY_RUN_STORAGE_KEY) === 'true';
  const getStoredMode = () => (storage.get(MODE_STORAGE_KEY) === 'standalone' ? 'standalone' : 'pathway');
  const getCompletedTutorials = () => storage.getJSON(STORAGE_KEY, {}) || {};
  const getStoredSelectedGoals = () => storage.getJSON(GOALS_STORAGE_KEY, null);
  const storeSelectedGoals = (keys) => storage.setJSON(GOALS_STORAGE_KEY, keys);

  function setTutorialMode(mode) {
    const cleanMode = mode === 'standalone' ? 'standalone' : 'pathway';
    storage.set(MODE_STORAGE_KEY, cleanMode);
    if (isTutorialsOverviewPage()) initNavigator();
    initWorkspaceLifecycle();
    updateFooterNavigation();
  }

  function setTutorialCompleted(tutorialKey, isCompleted) {
    const completed = getCompletedTutorials();
    if (isCompleted) completed[tutorialKey] = true;
    else delete completed[tutorialKey];
    storage.setJSON(STORAGE_KEY, completed);
  }

  const getEffectiveDuration = (tut, isDryRun) =>
    !tut ? '' : (isDryRun && tut.dry_run_duration) || tut.duration || '';

  function updateDryRunMode(isDryRun) {
    const active = Boolean(isDryRun);
    if (document.body) document.body.classList.toggle('tn-dry-run-active', active);
    document.querySelectorAll('.tn-dry-run-checkbox').forEach((cb) => { cb.checked = active; });
    document.querySelectorAll('.tn-dry-run-pref-card').forEach((card) => {
      card.classList.toggle('active', active);
      card.setAttribute('aria-checked', String(active));
    });

    const tutKey = getCurrentTutorialKey();
    const tut = tutKey && window.RAMBLE_TUTORIAL_DATA?.tutorials?.[tutKey];
    if (tut) {
      const suffix = active && tut.dry_run_duration ? ' (dry-run)' : '';
      const text = `⏱️ Estimated Time: ${getEffectiveDuration(tut, active)}${suffix}`;
      document.querySelectorAll('.tn-tut-duration-badge').forEach((b) => { b.textContent = text; });
    }
  }

  function setDryRun(isDryRun) {
    storage.set(DRY_RUN_STORAGE_KEY, isDryRun ? 'true' : 'false');
    updateDryRunMode(isDryRun);
  }

  function getAppFromElement(el) {
    const ignore = new Set([
      'tn-app-variant', 'tn-app-container', 'tn-app-switcher', 'tn-app-btn', 'tn-app-pref-card',
    ]);
    for (const cls of el?.classList || []) {
      if (cls.startsWith('tn-app-') && !ignore.has(cls)) return cls.slice('tn-app-'.length);
    }
    return null;
  }

  function updateAppVariants(selectedApp) {
    let activeApp = selectedApp;
    const variants = document.querySelectorAll('.tn-app-variant, .tn-app-container');
    if (variants.length > 0) {
      if (!document.querySelector(`.tn-app-variant.tn-app-${selectedApp}, .tn-app-container.tn-app-${selectedApp}`)) {
        for (const v of variants) {
          const app = getAppFromElement(v);
          if (app) { activeApp = app; break; }
        }
      }
      variants.forEach((el) => el.classList.toggle('active', el.classList.contains(`tn-app-${activeApp}`)));
    }
    if (document.body) document.body.dataset.selectedApp = activeApp;

    document.querySelectorAll('.tn-app-btn').forEach((btn) => {
      const isMatch = btn.getAttribute('data-app') === selectedApp;
      const checkEl = btn.querySelector('.tn-app-btn-check');
      btn.classList.toggle('active', isMatch);
      btn.setAttribute('aria-pressed', String(isMatch));
      if (checkEl) checkEl.textContent = isMatch ? '✓' : '';
    });

    document.querySelectorAll('.tn-app-pref-card').forEach((card) => {
      const isMatch = card.getAttribute('data-app') === selectedApp;
      const radio = card.querySelector('input[type="radio"]');
      card.classList.toggle('active', isMatch);
      card.setAttribute('aria-checked', String(isMatch));
      if (radio) radio.checked = isMatch;
    });

    const tutKey = getCurrentTutorialKey();
    if (tutKey) {
      const info = getTutorialWorkspaceInfo(tutKey, selectedApp);
      if (info) {
        updateWorkspacePromptControls(info);
        applyWorkspaceNameToSpans(info.currentName, info.isCustom);
      }
      initWorkspaceLifecycle();
    }
  }

  function setSelectedApp(appKey) {
    storage.set(APP_STORAGE_KEY, appKey);
    updateAppVariants(appKey);
  }

  const parseDurationToMinutes = (s) => parseInt(s?.match(/(\d+)/)?.[1] || '0', 10);

  function formatMinutes(minutes) {
    if (minutes < 60) return `${minutes} min`;
    const hrs = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return mins > 0 ? `${hrs}h ${mins}m` : `${hrs}h`;
  }

  function resolveDocUrl(relPath) {
    const attr = document.documentElement?.getAttribute('data-content_root');
    const root = attr || (window.location.pathname.replace(/\\/g, '/').includes('/tutorials/') ? '../' : './');
    const cleanRel = relPath.replace(/^\/+/, '');
    return !root || root === './' ? cleanRel : (root.endsWith('/') ? root : root + '/') + cleanRel;
  }

  const normalizeUrl = (url) => url.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '').replace(/\.html$/, '');

  function isTutorialsOverviewPage() {
    const norm = normalizeUrl(window.location.pathname);
    return norm.endsWith('/tutorials') || norm === 'tutorials';
  }

  function getGoalAverageWeight(goal, tutorials) {
    if (!goal?.tutorials?.length) return 999;
    const sum = goal.tutorials.reduce((acc, k) => acc + Number(tutorials?.[k]?.order_rank ?? 999), 0);
    return sum / goal.tutorials.length;
  }

  const getSortedGoalEntries = (goals, tutorials) =>
    goals ? Object.entries(goals).sort(([, a], [, b]) => getGoalAverageWeight(a, tutorials) - getGoalAverageWeight(b, tutorials)) : [];

  const getAllTutorialsSorted = (tutorials) =>
    Object.entries(tutorials || {})
      .map(([key, tut]) => ({ key, ...tut }))
      .sort((a, b) => (a.order_rank ?? 999) - (b.order_rank ?? 999));

  function getActivePathway(customGoalKeys) {
    if (!customGoalKeys && getStoredMode() === 'standalone') return [];
    const data = window.RAMBLE_TUTORIAL_DATA;
    if (!data?.tutorials || !data?.goals) return [];
    const { tutorials, goals } = data;

    let goalKeys = customGoalKeys ?? getStoredSelectedGoals();
    if (!Array.isArray(goalKeys)) {
      const sorted = getSortedGoalEntries(goals, tutorials);
      goalKeys = sorted.length > 0 ? [sorted[0][0]] : [];
    }
    if (goalKeys.length === 0) return [];

    const tutorialGoalMap = new Map();
    goalKeys.forEach((goalKey) => {
      (goals[goalKey]?.tutorials || []).forEach((tutKey) => {
        if (!tutorials[tutKey]) return;
        if (!tutorialGoalMap.has(tutKey)) tutorialGoalMap.set(tutKey, new Set());
        tutorialGoalMap.get(tutKey).add(goalKey);
      });
    });

    return Array.from(tutorialGoalMap.keys())
      .map((tutKey) => ({
        key: tutKey,
        ...tutorials[tutKey],
        requiredByGoals: Array.from(tutorialGoalMap.get(tutKey)),
      }))
      .sort((a, b) => (a.order_rank ?? 999) - (b.order_rank ?? 999));
  }

  function getCurrentTutorialKey() {
    const tutorials = window.RAMBLE_TUTORIAL_DATA?.tutorials;
    if (!tutorials) return null;
    const normCurrent = normalizeUrl(window.location.pathname);
    for (const [key, tut] of Object.entries(tutorials)) {
      if (!tut.url) continue;
      const normTut = normalizeUrl(tut.url);
      if (normCurrent.endsWith('/' + normTut) || normCurrent === normTut) return key;
    }
    return null;
  }

  function ensureFooterBtn(container, selector, className, accessKey, rel, insertFirst) {
    let btn = container.querySelector(selector);
    if (!btn) {
      btn = document.createElement('a');
      btn.className = className;
      btn.setAttribute('accesskey', accessKey);
      btn.setAttribute('rel', rel);
      btn.dataset.createdByTn = 'true';
      container.insertBefore(btn, insertFirst ? container.firstChild : null);
    } else if (btn.dataset.origHref === undefined) {
      btn.dataset.origHref = btn.getAttribute('href') || '';
      btn.dataset.origTitle = btn.getAttribute('title') || '';
      btn.dataset.origHtml = btn.innerHTML;
    }
    return btn;
  }

  function restoreFooterButtons(container) {
    if (!container) return;
    container.querySelectorAll('a').forEach((btn) => {
      if (btn.dataset.createdByTn === 'true') {
        btn.remove();
      } else if (btn.dataset.origHref !== undefined) {
        btn.setAttribute('href', btn.dataset.origHref);
        btn.setAttribute('title', btn.dataset.origTitle);
        btn.innerHTML = btn.dataset.origHtml;
        btn.classList.remove('btn-finish');
      }
    });
  }

  const formatGoalNames = (step) =>
    (step?.requiredByGoals || [])
      .map((k) => window.RAMBLE_TUTORIAL_DATA?.goals?.[k]?.title || k)
      .join(', ');

  function updateFooterNavigation() {
    const footerContainer = document.querySelector('.rst-footer-buttons');
    const data = window.RAMBLE_TUTORIAL_DATA;
    if (!footerContainer || !data?.tutorials || !data?.goals) return;

    const pathway = getActivePathway();
    const existingBar = document.querySelector('.tn-footer-pathway-bar');

    if (isTutorialsOverviewPage()) {
      existingBar?.remove();
      if (pathway.length > 0) {
        const firstTut = pathway[0];
        const nextBtn = ensureFooterBtn(footerContainer, 'a.float-right, a[rel="next"]', 'btn btn-neutral float-right', 'n', 'next', false);
        nextBtn.href = resolveDocUrl(firstTut.url);
        nextBtn.setAttribute('title', `Start Pathway: Step 1 - ${firstTut.title}`);
        nextBtn.innerHTML = `Start Pathway: Step 1 <span class="fa fa-arrow-circle-right" aria-hidden="true"></span>`;
        nextBtn.classList.remove('btn-finish');
      } else {
        restoreFooterButtons(footerContainer);
      }
      return;
    }

    const tutKey = getCurrentTutorialKey();
    const currentIndex = tutKey ? pathway.findIndex((t) => t.key === tutKey) : -1;
    if (currentIndex === -1) {
      existingBar?.remove();
      restoreFooterButtons(footerContainer);
      return;
    }

    const currentTut = pathway[currentIndex];
    const prevTut = currentIndex > 0 ? pathway[currentIndex - 1] : null;
    const nextTut = currentIndex < pathway.length - 1 ? pathway[currentIndex + 1] : null;

    let pathwayBar = existingBar;
    if (!pathwayBar) {
      pathwayBar = document.createElement('div');
      pathwayBar.className = 'tn-footer-pathway-bar';
      footerContainer.parentNode.insertBefore(pathwayBar, footerContainer);
    }

    const isCompleted = Boolean(getCompletedTutorials()[currentTut.key]);
    const goalNames = formatGoalNames(currentTut);

    pathwayBar.classList.toggle('step-done', isCompleted);
    pathwayBar.innerHTML = `
      <div class="tn-footer-pathway-info">
        <span class="tn-footer-pathway-badge">Active Learning Path</span>
        <span class="tn-footer-pathway-step"><strong>Step ${currentIndex + 1} of ${pathway.length}:</strong> ${currentTut.title}</span>
        ${goalNames ? `<span class="tn-footer-pathway-goals" title="Part of goal: ${goalNames}">(${goalNames})</span>` : ''}
      </div>
      <div class="tn-footer-pathway-actions">
        <label class="tn-footer-complete-toggle" title="Mark this step as completed">
          <input type="checkbox" class="tn-footer-complete-checkbox" ${isCompleted ? 'checked' : ''} />
          <span class="tn-footer-complete-label">Mark as Done</span>
        </label>
        <button type="button" class="tn-switch-standalone-btn" title="Exit learning pathway and show standalone instructions">📄 Stand-Alone Mode</button>
        <a href="${resolveDocUrl('tutorials.html')}" class="tn-footer-pathway-link" title="Return to Tutorials Overview to customize goals">Pathway Overview ↗</a>
      </div>
    `;

    pathwayBar.querySelector('.tn-footer-complete-checkbox')?.addEventListener('change', (e) => {
      setTutorialCompleted(currentTut.key, e.target.checked);
      pathwayBar.classList.toggle('step-done', e.target.checked);
    });

    const prevBtn = ensureFooterBtn(footerContainer, 'a.float-left, a[rel="prev"]', 'btn btn-neutral float-left', 'p', 'prev', true);
    prevBtn.href = resolveDocUrl(prevTut ? prevTut.url : 'tutorials.html');
    prevBtn.setAttribute('title', prevTut ? `Step ${currentIndex}: ${prevTut.title}` : 'Tutorials Overview & Pathway Selection');
    prevBtn.innerHTML = `<span class="fa fa-arrow-circle-left" aria-hidden="true"></span> ${prevTut ? `Previous: Step ${currentIndex}` : 'Tutorials Overview'}`;

    const nextBtn = ensureFooterBtn(footerContainer, 'a.float-right, a[rel="next"]', 'btn btn-neutral float-right', 'n', 'next', false);
    nextBtn.href = resolveDocUrl(nextTut ? nextTut.url : 'tutorials.html');
    nextBtn.setAttribute('title', nextTut ? `Step ${currentIndex + 2}: ${nextTut.title}` : 'Pathway Complete! Return to Tutorials Overview');
    nextBtn.innerHTML = nextTut
      ? `Next: Step ${currentIndex + 2} <span class="fa fa-arrow-circle-right" aria-hidden="true"></span>`
      : `Finish Pathway ✓ <span class="fa fa-check-circle" aria-hidden="true"></span>`;
    nextBtn.classList.toggle('btn-finish', !nextTut);
  }

  function initNavigator() {
    const container = document.getElementById('tutorial-navigator-app');
    const data = window.RAMBLE_TUTORIAL_DATA;
    if (!container || !data?.tutorials || !data?.goals) return;
    if (container._refresh) {
      container._refresh();
      return;
    }

    const { tutorials, goals } = data;
    const sortedGoalEntries = getSortedGoalEntries(goals, tutorials);
    const allTutorials = getAllTutorialsSorted(tutorials);
    let selectedGoalKeys = new Set();

    const modeGrid = container.querySelector('#tn-mode-grid');
    const goalsSection = container.querySelector('#tn-goals-section');
    const goalsList = container.querySelector('#tn-goals-list');
    const summaryBar = container.querySelector('#tn-summary-bar');
    const pathwayList = container.querySelector('#tn-pathway-list');
    const appsGrid = container.querySelector('#tn-apps-grid');
    const dryRunCard = container.querySelector('.tn-dry-run-pref-card');
    const appsHeading = container.querySelector('#tn-apps-heading');
    const dryRunHeading = container.querySelector('#tn-dry-run-heading');
    const pathwayHeading = container.querySelector('#tn-pathway-heading');

    function loadGoalKeysFromStorage() {
      let storedGoals = getStoredSelectedGoals();
      if (storedGoals === null) {
        storedGoals = sortedGoalEntries.length > 0 ? [sortedGoalEntries[0][0]] : [];
        storeSelectedGoals(storedGoals);
      }
      selectedGoalKeys = new Set(Array.isArray(storedGoals) ? storedGoals.filter((k) => goals[k]) : []);
    }

    function syncModeUI(mode) {
      const isStandalone = mode === 'standalone';
      modeGrid?.querySelectorAll('.tn-mode-card').forEach((card) => {
        const isMatch = card.getAttribute('data-mode') === mode;
        const radio = card.querySelector('input[type="radio"]');
        card.classList.toggle('active', isMatch);
        card.setAttribute('aria-checked', String(isMatch));
        if (radio) radio.checked = isMatch;
      });
      if (goalsSection) goalsSection.style.display = isStandalone ? 'none' : '';
      if (appsHeading) {
        appsHeading.textContent = `${isStandalone ? '1' : '2'}. Choose Preferred Application (for multi-application tutorials)`;
      }
      if (dryRunHeading) {
        dryRunHeading.textContent = `${isStandalone ? '2' : '3'}. Execution Mode (Dry-Run vs. Full Execution)`;
      }
      if (pathwayHeading) {
        pathwayHeading.textContent = isStandalone ? '3. Stand-Alone Tutorials' : '4. Recommended Learning Path';
      }
    }

    function syncGoalsUI() {
      goalsList?.querySelectorAll('.tn-goal-item').forEach((item) => {
        const isSelected = selectedGoalKeys.has(item.getAttribute('data-goal-key'));
        item.classList.toggle('selected', isSelected);
        item.setAttribute('aria-checked', String(isSelected));
        const cb = item.querySelector('input[type="checkbox"]');
        if (cb) cb.checked = isSelected;
      });
    }

    function renderTutorialCards(items, isStandalone, completedMap, isDryRun) {
      return items
        .map((tut, index) => {
          const isCompleted = Boolean(completedMap[tut.key]);
          const levelClass = (tut.level || 'beginner').toLowerCase();
          const effDuration = getEffectiveDuration(tut, isDryRun);
          const footerMeta = isStandalone
            ? `<span class="tn-goals-label">Mode:</span> <span class="tn-goal-tag">📄 Self-Contained Instructions</span>`
            : `<span class="tn-goals-label">Required for:</span> ${(tut.requiredByGoals || [])
                .map((gKey) => {
                  const g = goals[gKey];
                  return `<span class="tn-goal-tag">${g ? (g.icon ? g.icon + ' ' : '') + g.title : gKey}</span>`;
                })
                .join(' ')}`;

          return `
            <div class="tn-step-card ${isCompleted ? 'is-completed' : ''}" data-tutorial-key="${tut.key}">
              <div class="tn-step-num-col">
                <span class="tn-step-num">${isStandalone ? 'Tutorial' : `Step ${index + 1}`}</span>
                <label class="tn-complete-toggle" title="Mark as finished">
                  <input type="checkbox" class="tn-complete-checkbox" ${isCompleted ? 'checked' : ''} />
                  <span class="tn-complete-label">Done</span>
                </label>
              </div>
              <div class="tn-step-main">
                <div class="tn-step-header">
                  <a href="${tut.url}" class="tn-step-title-link">${tut.title}</a>
                  <div class="tn-step-badges">
                    <span class="tn-badge tn-badge-${levelClass}">${tut.level || 'Tutorial'}</span>
                    ${effDuration ? `<span class="tn-badge tn-badge-time">⏱️ ${effDuration}${isDryRun && tut.dry_run_duration ? ' (dry-run)' : ''}</span>` : ''}
                  </div>
                </div>
                <div class="tn-step-desc">${tut.description || ''}</div>
                <div class="tn-step-footer">
                  <div class="tn-step-goals">${footerMeta}</div>
                  <a href="${tut.url}" class="tn-btn tn-btn-open">Open Tutorial →</a>
                </div>
              </div>
            </div>
          `;
        })
        .join('');
    }

    function renderPathway() {
      if (!summaryBar || !pathwayList) return;
      const isStandalone = getStoredMode() === 'standalone';
      const completedMap = getCompletedTutorials();
      const isDryRun = getStoredDryRun();

      if (!isStandalone && selectedGoalKeys.size === 0) {
        summaryBar.innerHTML = `<div class="tn-empty-notice"><span>👈 Please select at least one end goal above to see your tutorial roadmap, or switch to <strong>Stand-Alone Tutorials</strong> mode above.</span></div>`;
        pathwayList.innerHTML = `<div class="tn-pathway-empty"><p>No goals selected. Choose what you want to achieve above to see recommended tutorials.</p></div>`;
        return;
      }

      const items = isStandalone ? allTutorials : getActivePathway(Array.from(selectedGoalKeys));
      const totalTutorials = items.length;
      let totalMinutes = 0;
      let completedCount = 0;

      items.forEach((tut) => {
        totalMinutes += parseDurationToMinutes(getEffectiveDuration(tut, isDryRun));
        if (completedMap[tut.key]) completedCount++;
      });
      const percent = totalTutorials > 0 ? Math.round((completedCount / totalTutorials) * 100) : 0;
      const firstMetric = isStandalone
        ? `<span class="tn-metric"><strong>📄 Stand-Alone Mode</strong> (No active learning pathway)</span>`
        : `<span class="tn-metric"><strong>${selectedGoalKeys.size}</strong> goal${selectedGoalKeys.size > 1 ? 's' : ''} selected</span>`;

      summaryBar.innerHTML = `
        <div class="tn-summary-content">
          <div class="tn-summary-metrics">
            ${firstMetric}
            <span class="tn-metric-dot">•</span>
            <span class="tn-metric"><strong>${totalTutorials}</strong> tutorial${totalTutorials > 1 ? 's' : ''} total</span>
            <span class="tn-metric-dot">•</span>
            <span class="tn-metric">Estimated time: <strong>${formatMinutes(totalMinutes)}${isDryRun ? ' (dry-run)' : ''}</strong></span>
            <span class="tn-metric-dot">•</span>
            <span class="tn-metric">Progress: <strong>${completedCount}/${totalTutorials}</strong> (${percent}%)</span>
          </div>
          <div class="tn-progress-bar-bg"><div class="tn-progress-bar-fill" style="width: ${percent}%;"></div></div>
        </div>
      `;

      pathwayList.innerHTML = renderTutorialCards(items, isStandalone, completedMap, isDryRun);
    }

    function updateGoalsSelection(newSet) {
      selectedGoalKeys = newSet;
      storeSelectedGoals(Array.from(selectedGoalKeys));
      syncGoalsUI();
      renderPathway();
      updateFooterNavigation();
    }

    modeGrid?.addEventListener('click', (e) => {
      const card = e.target.closest('.tn-mode-card');
      if (card) setTutorialMode(card.getAttribute('data-mode'));
    });
    bindKeyActivate(modeGrid, (e) => e.target.closest('.tn-mode-card'));

    goalsList?.addEventListener('click', (e) => {
      const item = e.target.closest('.tn-goal-item');
      if (!item) return;
      const key = item.getAttribute('data-goal-key');
      const next = new Set(selectedGoalKeys);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      updateGoalsSelection(next);
    });
    bindKeyActivate(goalsList, (e) => e.target.closest('.tn-goal-item'));

    container.querySelector('#tn-select-all-goals')?.addEventListener('click', () =>
      updateGoalsSelection(new Set(Object.keys(goals)))
    );
    container.querySelector('#tn-clear-goals')?.addEventListener('click', () =>
      updateGoalsSelection(new Set())
    );

    pathwayList?.addEventListener('change', (e) => {
      if (!e.target.classList.contains('tn-complete-checkbox')) return;
      const stepCard = e.target.closest('.tn-step-card');
      if (!stepCard) return;
      setTutorialCompleted(stepCard.getAttribute('data-tutorial-key'), e.target.checked);
      renderPathway();
      updateFooterNavigation();
    });

    appsGrid?.addEventListener('click', (e) => {
      const card = e.target.closest('.tn-app-pref-card');
      if (card) setSelectedApp(card.getAttribute('data-app'));
    });
    bindKeyActivate(appsGrid, (e) => e.target.closest('.tn-app-pref-card'));

    dryRunCard?.addEventListener('click', () => {
      setDryRun(!getStoredDryRun());
      renderPathway();
    });
    bindKeyActivate(dryRunCard);

    container._refresh = () => {
      loadGoalKeysFromStorage();
      syncModeUI(getStoredMode());
      syncGoalsUI();
      updateAppVariants(getStoredSelectedApp());
      updateDryRunMode(getStoredDryRun());
      renderPathway();
      updateFooterNavigation();
    };
    container._refresh();
  }

  function initAppSwitchers() {
    const data = window.RAMBLE_TUTORIAL_DATA || {};
    const switchers = Array.from(document.querySelectorAll('.tn-app-switcher'));
    const variants = document.querySelectorAll('.tn-app-variant, .tn-app-container');

    if (switchers.length === 0 && variants.length > 0) {
      const autoSwitcher = document.createElement('div');
      autoSwitcher.className = 'tn-app-switcher';
      variants[0].parentNode.insertBefore(autoSwitcher, variants[0]);
      switchers.push(autoSwitcher);
    }

    const currentApp = getStoredSelectedApp();
    switchers.forEach((switcher) => {
      const recipeId = switcher.getAttribute('data-recipe');
      const apps = data.recipes?.[recipeId]?.apps || data.selectable_applications || {};
      switcher.innerHTML = `
        <div class="tn-app-switcher-card">
          <div class="tn-app-switcher-header">
            <span class="tn-app-switcher-title">⚙️ Select Application:</span>
            <span class="tn-app-switcher-subtitle">Choose an application to customize all code examples and configurations in this tutorial:</span>
          </div>
          <div class="tn-app-btn-group" role="group" aria-label="Tutorial application switcher">
            ${Object.entries(apps)
              .map(([appKey, appInfo]) => {
                const isActive = appKey === currentApp;
                return `
                  <button type="button" class="tn-app-btn ${isActive ? 'active' : ''}" data-app="${appKey}" aria-pressed="${isActive}">
                    <span class="tn-app-btn-check">${isActive ? '✓' : ''}</span>
                    <span class="tn-app-btn-name">${appInfo.name || appKey}</span>
                    ${appInfo.workload ? `<span class="tn-app-btn-workload">${appInfo.workload}</span>` : ''}
                  </button>
                `;
              })
              .join('')}
          </div>
          <div class="tn-app-switcher-hint">
            💡 Selection is preserved across tutorials and automatically configures relevant commands and YAML configs.
          </div>
        </div>
      `;
      switcher.addEventListener('click', (e) => {
        const btn = e.target.closest('.tn-app-btn');
        if (btn) setSelectedApp(btn.getAttribute('data-app'));
      });
    });

    updateAppVariants(currentApp);
  }

  function getTutorialWorkspaceInfo(tutKey, selectedApp) {
    const tut = tutKey && window.RAMBLE_TUTORIAL_DATA?.tutorials?.[tutKey];
    if (!tut?.default_workspace_name) return null;

    const defaultTemplate = tut.default_workspace_name;
    const app = selectedApp || getStoredSelectedApp();
    const resolvedDefault = defaultTemplate.replace('{app}', app);

    const storedCustom =
      storage.get(WS_NAME_STORAGE_PREFIX + defaultTemplate) ||
      storage.get(WS_NAME_STORAGE_PREFIX + tutKey) ||
      (defaultTemplate === 'tutorial-workspace-{app}' ? storage.get(GLOBAL_WS_NAME_KEY) : null);

    const trimmed = storedCustom ? storedCustom.trim() : '';
    const isDefault =
      !trimmed || trimmed === resolvedDefault || trimmed === defaultTemplate || trimmed === 'tutorial-workspace';
    const rawCustom = isDefault ? null : trimmed;
    const currentName = rawCustom ? rawCustom.replace('{app}', app) : resolvedDefault;

    return {
      tutKey,
      defaultTemplate,
      resolvedDefault,
      currentName,
      isCustom: currentName !== resolvedDefault,
      rawCustom,
    };
  }

  function setTutorialWorkspaceName(tutKey, newName) {
    const info = getTutorialWorkspaceInfo(tutKey, getStoredSelectedApp());
    if (!info) return;
    const trimmed = (newName || '').trim();
    const isDefault =
      !trimmed ||
      trimmed === info.resolvedDefault ||
      trimmed === info.defaultTemplate ||
      trimmed === 'tutorial-workspace';

    const templateKey = WS_NAME_STORAGE_PREFIX + info.defaultTemplate;
    if (isDefault) {
      storage.remove(templateKey);
      storage.remove(WS_NAME_STORAGE_PREFIX + tutKey);
      if (info.defaultTemplate === 'tutorial-workspace-{app}') storage.remove(GLOBAL_WS_NAME_KEY);
    } else {
      storage.set(templateKey, trimmed);
    }
  }

  function tagWorkspaceNames(rootContainer, candidateNames) {
    const validCandidates = Array.from(
      new Set((candidateNames || []).filter((n) => typeof n === 'string' && n.length > 0))
    ).sort((a, b) => b.length - a.length);
    if (!rootContainer || validCandidates.length === 0) return;

    const escaped = validCandidates.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    const pattern = new RegExp(`(?<![a-zA-Z0-9_.-])(${escaped.join('|')})(?![a-zA-Z0-9_.-])`, 'g');
    const skipTags = new Set(['SCRIPT', 'STYLE', 'BUTTON', 'INPUT', 'TEXTAREA', 'SELECT']);

    const walker = document.createTreeWalker(rootContainer, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const parent = node.parentNode;
        if (!parent || skipTags.has(parent.nodeName.toUpperCase())) return NodeFilter.FILTER_REJECT;
        if (parent.closest?.('.tn-ws-prompt-card, .tn-ws-prompt-row, .tn-dry-run-row, .tn-ws-name')) {
          return NodeFilter.FILTER_REJECT;
        }
        return pattern.test(node.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
      },
    });

    const textNodes = [];
    while (walker.nextNode()) textNodes.push(walker.currentNode);

    textNodes.forEach((node) => {
      const text = node.nodeValue;
      pattern.lastIndex = 0;
      let match;
      let lastIdx = 0;
      const frag = document.createDocumentFragment();

      while ((match = pattern.exec(text)) !== null) {
        if (match.index > lastIdx) frag.appendChild(document.createTextNode(text.substring(lastIdx, match.index)));
        const span = document.createElement('span');
        span.className = 'tn-ws-name';
        span.setAttribute('data-default', match[1]);
        span.textContent = match[1];
        frag.appendChild(span);
        lastIdx = pattern.lastIndex;
      }
      if (lastIdx < text.length) frag.appendChild(document.createTextNode(text.substring(lastIdx)));
      node.parentNode?.replaceChild(frag, node);
    });
  }

  function applyWorkspaceNameToSpans(currentName, isCustom) {
    document.querySelectorAll('.tn-ws-name').forEach((span) => {
      span.textContent = currentName;
      span.classList.toggle('is-custom', Boolean(isCustom));
    });
  }

  function updateWorkspacePromptControls(info) {
    document.querySelectorAll('.tn-ws-input').forEach((input) => {
      input.value = info.isCustom ? info.rawCustom || info.currentName : info.currentName;
      input.placeholder = info.resolvedDefault;
      input.classList.toggle('is-custom', Boolean(info.isCustom));
    });
    document.querySelectorAll('.tn-ws-reset-btn').forEach((btn) => {
      btn.style.display = info.isCustom ? 'inline-flex' : 'none';
    });
  }

  function buildWsPromptRowHtml(info) {
    const val = info.isCustom ? info.rawCustom || info.currentName : info.currentName;
    return `
      <label class="tn-ws-prompt-label" for="tn-ws-name-input">📁 Workspace Name:</label>
      <div class="tn-ws-input-wrap">
        <input type="text" id="tn-ws-name-input" class="tn-ws-input" value="${val}" placeholder="${info.resolvedDefault}" spellcheck="false" autocomplete="off" />
      </div>
      <button type="button" class="tn-ws-reset-btn" id="tn-ws-reset-btn" title="Reset workspace name to default" style="display: ${info.isCustom ? 'inline-flex' : 'none'};">↺ Reset to Default</button>
      <div class="tn-ws-prompt-help">Customizing this updates commands, paths, and configs in this tutorial in real time.</div>
    `;
  }

  function initWorkspaceName() {
    const tutKey = getCurrentTutorialKey();
    const data = window.RAMBLE_TUTORIAL_DATA;
    const tut = tutKey && data?.tutorials?.[tutKey];
    if (!tut?.default_workspace_name) return;

    const templates = [tut.default_workspace_name, tut.static_workspace_name].filter(Boolean);
    const candidateNames = new Set(templates);
    templates.forEach((template) => {
      if (template.includes('{app}')) {
        candidateNames.add('tutorial-workspace');
        Object.keys(data.selectable_applications || { wrf: {}, gromacs: {}, hpl: {} }).forEach((app) =>
          candidateNames.add(template.replace('{app}', app))
        );
      }
    });

    const info = getTutorialWorkspaceInfo(tutKey, getStoredSelectedApp());
    if (!info) return;
    if (info.isCustom) candidateNames.add(info.currentName);

    const articleContainer =
      document.querySelector('div[itemprop="articleBody"]') || document.querySelector('.document') || document.body;
    tagWorkspaceNames(articleContainer, Array.from(candidateNames));

    const appSwitcherCard = document.querySelector('.tn-app-switcher-card');
    if (appSwitcherCard) {
      if (!appSwitcherCard.querySelector('.tn-ws-prompt-row')) {
        const row = document.createElement('div');
        row.className = 'tn-ws-prompt-row';
        row.innerHTML = buildWsPromptRowHtml(info);
        appSwitcherCard.appendChild(row);
      }
    } else if (!document.querySelector('.tn-ws-prompt-card')) {
      const codeBlocks = document.querySelectorAll('.highlight-console, .highlight-bash, .highlight');
      const promptTarget =
        document.querySelector('.tn-ws-prompt') ||
        Array.from(codeBlocks).find((b) => b.textContent.includes('workspace')) ||
        codeBlocks[0];
      if (promptTarget?.parentNode) {
        const card = document.createElement('div');
        card.className = 'tn-ws-prompt-card';
        card.innerHTML = `<div class="tn-ws-prompt-row">${buildWsPromptRowHtml(info)}</div>`;
        promptTarget.parentNode.insertBefore(card, promptTarget);
      }
    }

    document.querySelectorAll('.tn-ws-input').forEach((input) => {
      input.addEventListener('input', (e) => {
        const val = e.target.value.trim();
        const activeApp = getStoredSelectedApp();
        setTutorialWorkspaceName(tutKey, val);
        const updatedInfo = getTutorialWorkspaceInfo(tutKey, activeApp);
        const nameToUse = val ? val.replace('{app}', activeApp) : updatedInfo.resolvedDefault;

        document.querySelectorAll('.tn-ws-input').forEach((other) => {
          if (other !== input) other.value = e.target.value;
          other.placeholder = updatedInfo.resolvedDefault;
          other.classList.toggle('is-custom', Boolean(updatedInfo.isCustom));
        });
        document.querySelectorAll('.tn-ws-reset-btn').forEach((btn) => {
          btn.style.display = updatedInfo.isCustom ? 'inline-flex' : 'none';
        });
        applyWorkspaceNameToSpans(nameToUse, updatedInfo.isCustom);
        initWorkspaceLifecycle();
      });
    });

    document.querySelectorAll('.tn-ws-reset-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        setTutorialWorkspaceName(tutKey, null);
        const updatedInfo = getTutorialWorkspaceInfo(tutKey, getStoredSelectedApp());
        updateWorkspacePromptControls(updatedInfo);
        applyWorkspaceNameToSpans(updatedInfo.resolvedDefault, false);
        initWorkspaceLifecycle();
      });
    });

    applyWorkspaceNameToSpans(info.currentName, info.isCustom);
    updateWorkspacePromptControls(info);
  }

  function initDryRunControls() {
    const isDryRun = getStoredDryRun();
    updateDryRunMode(isDryRun);

    const tutKey = getCurrentTutorialKey();
    if (!tutKey) return;

    const tut = window.RAMBLE_TUTORIAL_DATA?.tutorials?.[tutKey];
    const hasDryRunBlocks = document.querySelector('.tn-dry-run-only, .tn-full-run-only') !== null;
    if (!tut?.dry_run_duration && !hasDryRunBlocks) return;

    let hostCard = document.querySelector('.tn-app-switcher-card, .tn-ws-prompt-card');
    if (!hostCard) {
      const firstBlock = document.querySelector('.tn-dry-run-only, .tn-full-run-only, .highlight-console');
      if (firstBlock?.parentNode) {
        hostCard = document.createElement('div');
        hostCard.className = 'tn-ws-prompt-card';
        firstBlock.parentNode.insertBefore(hostCard, firstBlock);
      }
    }
    if (!hostCard || hostCard.querySelector('.tn-dry-run-row')) return;

    const effDuration = getEffectiveDuration(tut, isDryRun);
    const row = document.createElement('div');
    row.className = 'tn-dry-run-row';
    row.innerHTML = `
      <label class="tn-dry-run-toggle">
        <input type="checkbox" class="tn-dry-run-checkbox" ${isDryRun ? 'checked' : ''} />
        <span>🧪 Enable Dry-Run Mode (<code>--dry-run</code>)</span>
      </label>
      ${effDuration ? `<span class="tn-tut-duration-badge">⏱️ Estimated Time: ${effDuration}${isDryRun && tut?.dry_run_duration ? ' (dry-run)' : ''}</span>` : ''}
      <div class="tn-dry-run-help">
        Runs <code>ramble workspace setup --dry-run</code>, skips executing (<code>ramble on</code>) and analyzing (<code>ramble workspace analyze</code>) experiments, and guides you through inspecting the generated experiment directories while showing example outputs for reference.
      </div>
    `;
    hostCard.appendChild(row);
    row.querySelector('.tn-dry-run-checkbox')?.addEventListener('change', (e) => setDryRun(e.target.checked));
  }

  function wrapOriginalContent(targetEl, noticeHtml, modifierClass) {
    if (!targetEl) return;
    let fallbackDetails = targetEl.querySelector('.tn-standalone-fallback');
    if (!fallbackDetails) {
      const heading = targetEl.querySelector('h1, h2, h3, h4, h5, h6');
      const nodesToWrap = Array.from(targetEl.childNodes).filter(
        (node) =>
          node !== heading &&
          !(node.nodeType === Node.ELEMENT_NODE &&
            (node.classList?.contains('tn-lifecycle-notice') || node.classList?.contains('tn-standalone-fallback')))
      );
      fallbackDetails = document.createElement('details');
      fallbackDetails.className = 'tn-standalone-fallback';
      fallbackDetails.innerHTML = '<summary>Show standalone instructions</summary><div class="tn-standalone-content"></div>';
      const contentDiv = fallbackDetails.querySelector('.tn-standalone-content');
      nodesToWrap.forEach((n) => contentDiv.appendChild(n));
      targetEl.appendChild(fallbackDetails);
    }

    let noticeEl = targetEl.querySelector('.tn-lifecycle-notice');
    if (!noticeEl) {
      noticeEl = document.createElement('div');
      targetEl.insertBefore(noticeEl, fallbackDetails);
    }
    noticeEl.className = `tn-lifecycle-notice ${modifierClass || ''}`;
    noticeEl.innerHTML = noticeHtml;
  }

  function unwrapOriginalContent(targetEl) {
    if (!targetEl) return;
    targetEl.querySelector('.tn-lifecycle-notice')?.remove();
    const fallbackDetails = targetEl.querySelector('.tn-standalone-fallback');
    if (fallbackDetails) {
      const contentDiv = fallbackDetails.querySelector('.tn-standalone-content');
      while (contentDiv?.firstChild) targetEl.insertBefore(contentDiv.firstChild, fallbackDetails);
      fallbackDetails.remove();
    }
  }

  const buildLifecycleNotice = (badge, title, bodyHtml) => `
    <div class="tn-lifecycle-header">
      <span class="tn-lifecycle-badge">${badge}</span>
      <span>${title}</span>
      <button type="button" class="tn-switch-standalone-btn" title="Switch to Stand-Alone mode to view self-contained instructions without pathway notices">📄 Switch to Stand-Alone</button>
    </div>
    <div class="tn-lifecycle-body">${bodyHtml}</div>
  `;

  function applyResourceLifecycle(pathway, currentIndex, cfg) {
    const curStep = pathway[currentIndex];
    const goalNames = formatGoalNames(curStep);
    const lower = cfg.label.toLowerCase();

    document.querySelectorAll(cfg.createSelector).forEach((el) => {
      if (!cfg.isActive || !cfg.isReusedFromEarlier(pathway, currentIndex, curStep)) {
        unwrapOriginalContent(el);
        return;
      }
      const html = buildLifecycleNotice(
        'Active Learning Path',
        `${cfg.label} Already Configured`,
        `
          <p>In a standalone scenario where you started directly with this tutorial, you would create and ${cfg.createAction} from scratch:</p>
          <div class="tn-hypothetical-code">${cfg.createCmdHtml}</div>
          <div class="tn-lifecycle-action-callout">
            <strong>✓ ${cfg.label} Ready:</strong> You already created and ${cfg.configuredVerb} <code>${cfg.nameHtml}</code> earlier in this learning path.
            <p>${cfg.verifyPrompt}</p>
            <div class="tn-actionable-code">${cfg.verifyCmdHtml}</div>
            <p>If <code>${cfg.nameHtml}</code> is already ${cfg.activeAdj.toLowerCase()} from the previous step, you can continue directly to the next section!</p>
          </div>
          <div class="tn-lifecycle-action-callout">
            <strong>🔄 Alternative — Start Clean:</strong> If you wish to remove the existing ${lower} first and start clean in this tutorial, run:
            <div class="tn-actionable-code">${cfg.startCleanCmdHtml}</div>
            ${cfg.cleanExtraNote || ''}
          </div>
        `
      );
      wrapOriginalContent(el, html, 'notice-reuse');
    });

    document.querySelectorAll(cfg.cleanupSelector).forEach((el) => {
      if (!cfg.isActive) return;
      if (cfg.isFinalStep(pathway, currentIndex)) {
        const html = buildLifecycleNotice(
          'Pathway Complete',
          `🎉 Consolidated ${cfg.label} Cleanup`,
          `
            <p>${cfg.consolidatedIntro(goalNames)}</p>
            <div class="tn-actionable-code">${cfg.consolidatedCmdsHtml(pathway)}</div>
            <p>If you wish to retain your ${cfg.retainWhat}, you can safely skip the ${lower} removal commands above.</p>
          `
        );
        wrapOriginalContent(el, html, 'notice-consolidated');
      } else {
        const reusedNext = cfg.isReusedInFuture(pathway, currentIndex, curStep);
        const title = reusedNext
          ? `Keep ${cfg.label} ${cfg.activeAdj} for Next Steps`
          : `Keep ${cfg.label} ${cfg.activeAdj} Until Pathway Completion`;
        const calloutHtml = reusedNext
          ? `<strong>⚠️ Pathway Action: Do NOT remove this ${lower} yet!</strong><p>${cfg.keepForNextBody(goalNames)}</p><p>A consolidated ${lower} cleanup will be provided at the end of your learning path.</p>`
          : `<strong>💡 Pathway Notice:</strong> You can leave this ${lower} in place and continue along your learning path. All ${cfg.plural} created along this pathway will be cleaned up together at the end of the learning path.`;
        const html = buildLifecycleNotice(
          'Active Learning Path',
          title,
          `
            <p>In a standalone scenario where you are not following a multi-step pathway, you would clean up by ${cfg.cleanupVerb} the ${lower} at this point:</p>
            <div class="tn-hypothetical-code">${cfg.singleCleanupCmdHtml}</div>
            <div class="tn-lifecycle-action-callout">${calloutHtml}</div>
          `
        );
        wrapOriginalContent(el, html, 'notice-hypothetical');
      }
    });
  }

  function initWorkspaceLifecycle() {
    const tutKey = getCurrentTutorialKey();
    const data = window.RAMBLE_TUTORIAL_DATA;
    if (!tutKey || !data?.tutorials) return;

    const pathway = getActivePathway();
    const currentIndex = pathway.findIndex((t) => t.key === tutKey);
    if (currentIndex === -1) {
      document
        .querySelectorAll('.tn-workspace-create, .tn-workspace-cleanup, .tn-repo-create, .tn-repo-cleanup')
        .forEach(unwrapOriginalContent);
      return;
    }

    const curStep = pathway[currentIndex];
    const repoName = curStep?.default_repo_name || 'tutorial-repo';

    applyResourceLifecycle(pathway, currentIndex, {
      label: 'Repository',
      plural: 'repositories',
      activeAdj: 'Registered',
      configuredVerb: 'registered',
      createAction: 'register a new object repository',
      cleanupVerb: 'unregistering and removing',
      retainWhat: 'custom object definitions for future use',
      isActive: Boolean(curStep?.default_repo_name),
      createSelector: '.tn-repo-create',
      cleanupSelector: '.tn-repo-cleanup',
      nameHtml: repoName,
      createCmdHtml: `$ ramble repo create ${repoName}<br />$ ramble repo add ${repoName}`,
      verifyPrompt: 'You can verify that it is still registered in your environment with:',
      verifyCmdHtml: '$ ramble repo list',
      startCleanCmdHtml: `$ ramble repo rm ${repoName}<br />$ rm -rf ${repoName}<br />$ ramble repo create ${repoName}<br />$ ramble repo add ${repoName}`,
      singleCleanupCmdHtml: `$ ramble repo rm ${repoName}<br />$ rm -rf ${repoName}`,
      isReusedFromEarlier(pw, idx, step) {
        const prevIdx = step.reuses_repo_from ? pw.findIndex((t) => t.key === step.reuses_repo_from) : -1;
        return (prevIdx !== -1 && prevIdx < idx) || pw.slice(0, idx).some((t) => t.default_repo_name === repoName);
      },
      isFinalStep: (pw, idx) => !pw.slice(idx + 1).some((t) => Boolean(t.default_repo_name)),
      isReusedInFuture: () => true,
      consolidatedIntro: (goals) =>
        `Now that you have finished all repository exercises in the <strong>${goals || 'recommended'}</strong> learning path, you can unregister and remove the custom repository created during your journey:`,
      consolidatedCmdsHtml(pw) {
        const repos = Array.from(new Set(pw.map((s) => s.default_repo_name).filter(Boolean)));
        if (repos.length === 0) repos.push(repoName);
        return repos.map((r) => `$ ramble repo rm <strong>${r}</strong><br />$ rm -rf <strong>${r}</strong>`).join('<br />');
      },
      keepForNextBody: (goals) =>
        `Because you are following the <strong>${goals || 'Active'}</strong> learning path, subsequent tutorials will also use the <code>${repoName}</code> repository. Keep <code>${repoName}</code> registered and proceed to the next tutorial.`,
    });

    const currentApp = getStoredSelectedApp();
    const info = getTutorialWorkspaceInfo(tutKey, currentApp);
    if (!info) return;

    const currentName = info.currentName;
    const isDirMode = Boolean(curStep?.workspace_dir_mode);
    const dirFlag = isDirMode ? '-d ' : '';
    const wsSpan = `<span class="tn-ws-name">${currentName}</span>`;
    const createCmd = `$ ramble workspace create ${dirFlag}${wsSpan}`;
    const activateCmd = `$ ramble workspace activate ${dirFlag}${wsSpan}`;
    const removeCmd = isDirMode ? `$ rm -rf ${wsSpan}` : `$ ramble workspace remove ${wsSpan}`;

    const matchesStepWs = (otherStep) => {
      const otherInfo = getTutorialWorkspaceInfo(otherStep.key, currentApp);
      return (
        !isDirMode &&
        !otherStep.workspace_dir_mode &&
        otherInfo?.currentName === currentName &&
        otherStep.default_workspace_name === curStep.default_workspace_name
      );
    };

    applyResourceLifecycle(pathway, currentIndex, {
      label: 'Workspace',
      plural: 'workspaces',
      activeAdj: 'Active',
      configuredVerb: 'configured',
      createAction: 'configure a new workspace',
      cleanupVerb: 'deactivating and removing',
      retainWhat: 'experiment configurations or generated results for future exploration',
      isActive: true,
      createSelector: '.tn-workspace-create',
      cleanupSelector: '.tn-workspace-cleanup',
      nameHtml: wsSpan,
      createCmdHtml: createCmd,
      verifyPrompt: 'To continue with this tutorial, ensure the workspace is active in your current shell:',
      verifyCmdHtml: activateCmd,
      startCleanCmdHtml: `$ ramble workspace deactivate<br />${removeCmd}<br />${createCmd}<br />${activateCmd}`,
      singleCleanupCmdHtml: `$ ramble workspace deactivate<br />${removeCmd}`,
      cleanExtraNote:
        curStep?.key === 'modify_experiment'
          ? '<p><em>Note: This tutorial modifies the experiment configured in Creating a Single Experiment Workspace, so if you start clean you will need to re-add that experiment first.</em></p>'
          : '',
      isReusedFromEarlier(pw, idx, step) {
        const prevIdx = step.reuses_workspace_from ? pw.findIndex((t) => t.key === step.reuses_workspace_from) : -1;
        return (prevIdx !== -1 && prevIdx < idx) || pw.slice(0, idx).some(matchesStepWs);
      },
      isFinalStep: (pw, idx) => idx === pw.length - 1 || !pw.slice(idx + 1).some((t) => Boolean(t.default_workspace_name)),
      isReusedInFuture: (pw, idx, step) =>
        pw.slice(idx + 1).some((t) => t.reuses_workspace_from === step.key || matchesStepWs(t)),
      consolidatedIntro: (goals) =>
        `Congratulations on completing the <strong>${goals || 'recommended'}</strong> learning path! Now that you have finished all workspace exercises, you can clean up all workspaces created during your journey:`,
      consolidatedCmdsHtml(pw) {
        const seen = new Set();
        const cmds = ['$ ramble workspace deactivate'];
        pw.forEach((step) => {
          const sInfo = getTutorialWorkspaceInfo(step.key, currentApp);
          const stepDir = Boolean(step.workspace_dir_mode);
          const key = sInfo?.currentName ? `${stepDir ? 'dir:' : 'named:'}${sInfo.currentName}` : null;
          if (key && !seen.has(key)) {
            seen.add(key);
            if (step.key === 'workspace_config_cmd') {
              cmds.push(`$ rm -rf <strong>${sInfo.currentName} squash-workspace</strong>`);
            } else {
              cmds.push(stepDir ? `$ rm -rf <strong>${sInfo.currentName}</strong>` : `$ ramble workspace remove <strong>${sInfo.currentName}</strong>`);
            }
          }
        });
        return cmds.join('<br />');
      },
      keepForNextBody: (goals) =>
        `Because you are following the <strong>${goals || 'Active'}</strong> learning path, subsequent tutorial content builds directly upon this workspace. Keep <code>${wsSpan}</code> intact and proceed to the next tutorial.`,
    });

    applyWorkspaceNameToSpans(info.currentName, info.isCustom);
  }

  window.addEventListener('storage', (e) => {
    if (e.key === THEME_STORAGE_KEY) {
      applyTheme(getEffectiveTheme());
    } else if (e.key === APP_STORAGE_KEY) {
      updateAppVariants(e.newValue || DEFAULT_APP);
    } else if (e.key === DRY_RUN_STORAGE_KEY) {
      updateDryRunMode(e.newValue === 'true');
      if (isTutorialsOverviewPage()) initNavigator();
    } else if (e.key === GOALS_STORAGE_KEY || e.key === STORAGE_KEY || e.key === MODE_STORAGE_KEY) {
      if (isTutorialsOverviewPage()) initNavigator();
      updateFooterNavigation();
      initWorkspaceLifecycle();
    } else if (e.key === GLOBAL_WS_NAME_KEY || e.key?.startsWith(WS_NAME_STORAGE_PREFIX)) {
      const tutKey = getCurrentTutorialKey();
      const info = tutKey ? getTutorialWorkspaceInfo(tutKey) : null;
      if (info) {
        updateWorkspacePromptControls(info);
        applyWorkspaceNameToSpans(info.currentName, info.isCustom);
        initWorkspaceLifecycle();
      }
    }
  });

  function initializeAll() {
    document.addEventListener('click', (e) => {
      if (e.target.closest?.('.tn-switch-standalone-btn')) {
        setTutorialMode('standalone');
      } else if (e.target.closest?.('.tn-theme-toggle-btn')) {
        setTheme(getEffectiveTheme() === 'dark' ? 'light' : 'dark');
      }
    });
    initTheme();
    initNavigator();
    initAppSwitchers();
    initWorkspaceName();
    initDryRunControls();
    initWorkspaceLifecycle();
    updateFooterNavigation();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAll);
  } else {
    initializeAll();
  }
})();
