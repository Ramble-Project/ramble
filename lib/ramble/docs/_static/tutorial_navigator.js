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

  const KNOWN_WORKSPACE_NAMES = [
    'tutorial-workspace',
    'tutorial-workspace-wrf',
    'tutorial-workspace-gromacs',
    'tutorial-workspace-hpl',
    'hello_world',
    'manage-workspace',
    'includes-workspace',
    'squash-workspace',
    'test-sys-plat',
    'wrf_mirror_test',
    'eessi_gromacs',
    'basic_wrf',
    'basic_gromacs',
    'basic_hpl',
    'vectors_wrf',
    'vectors_gromacs',
    'vectors_hpl',
    'software_wrf',
    'software_gromacs',
    'software_hpl',
    'scaling_wrf',
    'scaling_gromacs',
    'scaling_hpl',
    'success_wrf',
    'success_gromacs',
    'success_hpl',
    'modifiers_wrf',
    'modifiers_gromacs',
    'modifiers_hpl',
    'zips_wrf',
    'zips_gromacs',
    'zips_hpl',
    'var_expansion_wrf',
    'var_expansion_gromacs',
    'var_expansion_hpl',
    'internals_wrf',
    'internals_gromacs',
    'internals_hpl',
  ];

  function getStoredSelectedApp() {
    try {
      const stored = localStorage.getItem(APP_STORAGE_KEY);
      return stored || DEFAULT_APP;
    } catch (e) {
      return DEFAULT_APP;
    }
  }

  function storeSelectedApp(appKey) {
    try {
      localStorage.setItem(APP_STORAGE_KEY, appKey);
    } catch (e) {
      console.warn('Could not save selected application:', e);
    }
  }

  function getStoredDryRun() {
    try {
      return localStorage.getItem(DRY_RUN_STORAGE_KEY) === 'true';
    } catch (e) {
      return false;
    }
  }

  function storeDryRun(isDryRun) {
    try {
      localStorage.setItem(DRY_RUN_STORAGE_KEY, isDryRun ? 'true' : 'false');
    } catch (e) {
      console.warn('Could not save dry-run preference:', e);
    }
  }

  function getEffectiveDuration(tut, isDryRun) {
    if (!tut) return '';
    if (isDryRun && tut.dry_run_duration) {
      return tut.dry_run_duration;
    }
    return tut.duration || '';
  }

  function updateDryRunMode(isDryRun) {
    const active = !!isDryRun;
    if (document.body) {
      document.body.classList.toggle('tn-dry-run-active', active);
    }

    document.querySelectorAll('.tn-dry-run-checkbox').forEach((cb) => {
      cb.checked = active;
    });

    document.querySelectorAll('.tn-dry-run-pref-card').forEach((card) => {
      card.classList.toggle('active', active);
      card.setAttribute('aria-checked', String(active));
    });

    const tutKey = getCurrentTutorialKey();
    const data = window.RAMBLE_TUTORIAL_DATA;
    const tut = tutKey && data && data.tutorials ? data.tutorials[tutKey] : null;
    if (tut) {
      const effDuration = getEffectiveDuration(tut, active);
      document.querySelectorAll('.tn-tut-duration-badge').forEach((badge) => {
        badge.textContent = `⏱️ Estimated Time: ${effDuration}${active && tut.dry_run_duration ? ' (dry-run)' : ''}`;
      });
    }
  }

  function setDryRun(isDryRun) {
    storeDryRun(isDryRun);
    updateDryRunMode(isDryRun);
  }

  function getAppFromElement(el) {
    if (!el || !el.classList) return null;
    for (const cls of el.classList) {
      if (
        cls.startsWith('tn-app-') &&
        cls !== 'tn-app-variant' &&
        cls !== 'tn-app-container' &&
        cls !== 'tn-app-switcher' &&
        cls !== 'tn-app-btn' &&
        cls !== 'tn-app-pref-card'
      ) {
        return cls.replace('tn-app-', '');
      }
    }
    return null;
  }

  function updateAppVariants(selectedApp) {
    // 1. Update all variant containers on page
    const variants = document.querySelectorAll('.tn-app-variant, .tn-app-container');
    if (variants.length > 0) {
      let activeApp = selectedApp;
      const hasMatch = document.querySelector(
        `.tn-app-variant.tn-app-${selectedApp}, .tn-app-container.tn-app-${selectedApp}`
      );
      if (!hasMatch) {
        for (const v of variants) {
          const app = getAppFromElement(v);
          if (app) {
            activeApp = app;
            break;
          }
        }
      }

      variants.forEach((el) => {
        if (el.classList.contains(`tn-app-${activeApp}`)) {
          el.classList.add('active');
          el.style.setProperty('display', 'block', 'important');
        } else {
          el.classList.remove('active');
          el.style.setProperty('display', 'none', 'important');
        }
      });
    }

    // 2. Update all app buttons and cards across document
    document.querySelectorAll('.tn-app-btn').forEach((btn) => {
      const app = btn.getAttribute('data-app');
      const checkEl = btn.querySelector('.tn-app-btn-check');
      if (app === selectedApp) {
        btn.classList.add('active');
        btn.setAttribute('aria-pressed', 'true');
        if (checkEl) checkEl.textContent = '✓';
      } else {
        btn.classList.remove('active');
        btn.setAttribute('aria-pressed', 'false');
        if (checkEl) checkEl.textContent = '';
      }
    });

    document.querySelectorAll('.tn-app-pref-card').forEach((card) => {
      const app = card.getAttribute('data-app');
      const radio = card.querySelector('input[type="radio"]');
      if (app === selectedApp) {
        card.classList.add('active');
        card.setAttribute('aria-checked', 'true');
        if (radio) radio.checked = true;
      } else {
        card.classList.remove('active');
        card.setAttribute('aria-checked', 'false');
        if (radio) radio.checked = false;
      }
    });

    // 3. Update workspace prompt if template contains {app}
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
    storeSelectedApp(appKey);
    updateAppVariants(appKey);
  }

  function getCompletedTutorials() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : {};
    } catch (e) {
      return {};
    }
  }

  function setTutorialCompleted(tutorialKey, isCompleted) {
    try {
      const completed = getCompletedTutorials();
      if (isCompleted) {
        completed[tutorialKey] = true;
      } else {
        delete completed[tutorialKey];
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(completed));
    } catch (e) {
      console.warn('Could not save tutorial progress:', e);
    }
  }

  function getStoredSelectedGoals() {
    try {
      const stored = localStorage.getItem(GOALS_STORAGE_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch (e) {
      return null;
    }
  }

  function storeSelectedGoals(selectedKeys) {
    try {
      localStorage.setItem(GOALS_STORAGE_KEY, JSON.stringify(selectedKeys));
    } catch (e) {
      console.warn('Could not save selected goals:', e);
    }
  }

  function parseDurationToMinutes(durationStr) {
    if (!durationStr) return 0;
    const match = durationStr.match(/(\d+)/);
    return match ? parseInt(match[1], 10) : 0;
  }

  function formatMinutes(minutes) {
    if (minutes < 60) {
      return `${minutes} min`;
    }
    const hrs = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return mins > 0 ? `${hrs}h ${mins}m` : `${hrs}h`;
  }

  function getContentRoot() {
    const html = document.documentElement;
    const attr = html ? html.getAttribute('data-content_root') : null;
    if (attr !== null && attr !== undefined && attr !== '') {
      return attr;
    }
    const path = window.location.pathname.replace(/\\/g, '/');
    if (path.includes('/tutorials/')) {
      return '../';
    }
    return './';
  }

  function resolveDocUrl(relPath) {
    const root = getContentRoot();
    const cleanRel = relPath.replace(/^\/+/, '');
    if (!root || root === './') {
      return cleanRel;
    }
    if (root.endsWith('/')) {
      return root + cleanRel;
    }
    return root + '/' + cleanRel;
  }

  function normalizeUrl(url) {
    return url
      .replace(/\\/g, '/')
      .replace(/^\/+/, '')
      .replace(/\/+$/, '')
      .replace(/\.html$/, '');
  }

  function isTutorialsOverviewPage() {
    const norm = normalizeUrl(window.location.pathname);
    return norm.endsWith('/tutorials') || norm === 'tutorials';
  }

  function getActivePathway(customGoalKeys) {
    const data = window.RAMBLE_TUTORIAL_DATA;
    if (!data || !data.tutorials || !data.goals) {
      return [];
    }
    const tutorials = data.tutorials;
    const goals = data.goals;

    let goalKeys = customGoalKeys;
    if (!goalKeys) {
      const stored = getStoredSelectedGoals();
      if (Array.isArray(stored)) {
        goalKeys = stored;
      } else {
        const firstGoal = Object.keys(goals)[0];
        goalKeys = firstGoal ? [firstGoal] : [];
      }
    }

    if (goalKeys.length === 0) {
      return [];
    }

    const tutorialGoalMap = new Map();
    goalKeys.forEach((goalKey) => {
      const goal = goals[goalKey];
      if (!goal || !Array.isArray(goal.tutorials)) return;

      goal.tutorials.forEach((tutKey) => {
        if (!tutorials[tutKey]) return;
        if (!tutorialGoalMap.has(tutKey)) {
          tutorialGoalMap.set(tutKey, new Set());
        }
        tutorialGoalMap.get(tutKey).add(goalKey);
      });
    });

    return Array.from(tutorialGoalMap.keys())
      .map((tutKey) => ({
        key: tutKey,
        ...tutorials[tutKey],
        requiredByGoals: Array.from(tutorialGoalMap.get(tutKey)),
      }))
      .sort((a, b) => {
        const rankA = a.order_rank !== undefined ? a.order_rank : 999;
        const rankB = b.order_rank !== undefined ? b.order_rank : 999;
        return rankA - rankB;
      });
  }

  function findCurrentTutorialIndex(pathway) {
    const currentPath = window.location.pathname.replace(/\\/g, '/');
    const normCurrent = normalizeUrl(currentPath);
    for (let i = 0; i < pathway.length; i++) {
      const tut = pathway[i];
      if (!tut.url) continue;
      const normTut = normalizeUrl(tut.url);
      if (normCurrent.endsWith('/' + normTut) || normCurrent.endsWith(normTut)) {
        return i;
      }
    }
    return -1;
  }

  function getCurrentTutorialKey() {
    const data = window.RAMBLE_TUTORIAL_DATA;
    if (!data || !data.tutorials) return null;
    const currentPath = window.location.pathname.replace(/\\/g, '/');
    const normCurrent = normalizeUrl(currentPath);
    for (const [key, tut] of Object.entries(data.tutorials)) {
      if (!tut.url) continue;
      const normTut = normalizeUrl(tut.url);
      if (normCurrent.endsWith('/' + normTut) || normCurrent.endsWith(normTut)) {
        return key;
      }
    }
    return null;
  }

  function updateFooterNavigation() {
    const footerContainer = document.querySelector('.rst-footer-buttons');
    if (!footerContainer) {
      return;
    }

    const data = window.RAMBLE_TUTORIAL_DATA;
    if (!data || !data.tutorials || !data.goals) {
      return;
    }

    const pathway = getActivePathway();
    const isOverview = isTutorialsOverviewPage();

    if (isOverview) {
      const existingBar = document.querySelector('.tn-footer-pathway-bar');
      if (existingBar) existingBar.remove();

      if (pathway.length > 0) {
        let nextBtn = footerContainer.querySelector('a.float-right, a[rel="next"]');
        if (!nextBtn) {
          nextBtn = document.createElement('a');
          nextBtn.className = 'btn btn-neutral float-right';
          nextBtn.setAttribute('accesskey', 'n');
          nextBtn.setAttribute('rel', 'next');
          footerContainer.appendChild(nextBtn);
        }
        const firstTut = pathway[0];
        nextBtn.href = resolveDocUrl(firstTut.url);
        nextBtn.setAttribute('title', `Start Pathway: Step 1 - ${firstTut.title}`);
        nextBtn.innerHTML = `Start Pathway: Step 1 <span class="fa fa-arrow-circle-right" aria-hidden="true"></span>`;
        nextBtn.classList.remove('btn-finish');

        const headNext = document.querySelector('link[rel="next"]');
        if (headNext) {
          headNext.href = resolveDocUrl(firstTut.url);
          headNext.setAttribute('title', firstTut.title);
        }
      }
      return;
    }

    const currentIndex = findCurrentTutorialIndex(pathway);
    if (currentIndex === -1) {
      const existingBar = document.querySelector('.tn-footer-pathway-bar');
      if (existingBar) existingBar.remove();
      return;
    }

    const currentTut = pathway[currentIndex];
    const prevTut = currentIndex > 0 ? pathway[currentIndex - 1] : null;
    const nextTut = currentIndex < pathway.length - 1 ? pathway[currentIndex + 1] : null;

    // 1. Render or update Pathway Status Bar
    let pathwayBar = document.querySelector('.tn-footer-pathway-bar');
    if (!pathwayBar) {
      pathwayBar = document.createElement('div');
      pathwayBar.className = 'tn-footer-pathway-bar';
      footerContainer.parentNode.insertBefore(pathwayBar, footerContainer);
    }

    const completedMap = getCompletedTutorials();
    const isCompleted = !!completedMap[currentTut.key];

    const goalNames = (currentTut.requiredByGoals || [])
      .map((gKey) => (data.goals[gKey] ? data.goals[gKey].title : gKey))
      .join(', ');

    pathwayBar.innerHTML = `
      <div class="tn-footer-pathway-info">
        <span class="tn-footer-pathway-badge">Active Learning Path</span>
        <span class="tn-footer-pathway-step">
          <strong>Step ${currentIndex + 1} of ${pathway.length}:</strong> ${currentTut.title}
        </span>
        ${goalNames ? `<span class="tn-footer-pathway-goals" title="Part of goal: ${goalNames}">(${goalNames})</span>` : ''}
      </div>
      <div class="tn-footer-pathway-actions">
        <label class="tn-footer-complete-toggle" title="Mark this step as completed">
          <input type="checkbox" class="tn-footer-complete-checkbox" ${isCompleted ? 'checked' : ''} />
          <span class="tn-footer-complete-label">Mark as Done</span>
        </label>
        <a href="${resolveDocUrl('tutorials.html')}" class="tn-footer-pathway-link" title="Return to Tutorials Overview to customize goals">
          Pathway Overview ↗
        </a>
      </div>
    `;

    const doneBox = pathwayBar.querySelector('.tn-footer-complete-checkbox');
    if (doneBox) {
      doneBox.addEventListener('change', (e) => {
        setTutorialCompleted(currentTut.key, e.target.checked);
        if (e.target.checked) {
          pathwayBar.classList.add('step-done');
        } else {
          pathwayBar.classList.remove('step-done');
        }
      });
      if (isCompleted) {
        pathwayBar.classList.add('step-done');
      } else {
        pathwayBar.classList.remove('step-done');
      }
    }

    // 2. Update Previous Button
    let prevBtn = footerContainer.querySelector('a.float-left, a[rel="prev"]');
    if (!prevBtn) {
      prevBtn = document.createElement('a');
      prevBtn.className = 'btn btn-neutral float-left';
      prevBtn.setAttribute('accesskey', 'p');
      prevBtn.setAttribute('rel', 'prev');
      footerContainer.insertBefore(prevBtn, footerContainer.firstChild);
    }

    if (prevTut) {
      prevBtn.href = resolveDocUrl(prevTut.url);
      prevBtn.setAttribute('title', `Step ${currentIndex}: ${prevTut.title}`);
      prevBtn.innerHTML = `<span class="fa fa-arrow-circle-left" aria-hidden="true"></span> Previous: Step ${currentIndex}`;
    } else {
      prevBtn.href = resolveDocUrl('tutorials.html');
      prevBtn.setAttribute('title', 'Tutorials Overview & Pathway Selection');
      prevBtn.innerHTML = `<span class="fa fa-arrow-circle-left" aria-hidden="true"></span> Tutorials Overview`;
    }

    const headPrev = document.querySelector('link[rel="prev"]');
    if (headPrev) {
      headPrev.href = prevTut ? resolveDocUrl(prevTut.url) : resolveDocUrl('tutorials.html');
      headPrev.setAttribute('title', prevTut ? prevTut.title : 'Tutorials Overview');
    }

    // 3. Update Next Button
    let nextBtn = footerContainer.querySelector('a.float-right, a[rel="next"]');
    if (!nextBtn) {
      nextBtn = document.createElement('a');
      nextBtn.className = 'btn btn-neutral float-right';
      nextBtn.setAttribute('accesskey', 'n');
      nextBtn.setAttribute('rel', 'next');
      footerContainer.appendChild(nextBtn);
    }

    if (nextTut) {
      nextBtn.href = resolveDocUrl(nextTut.url);
      nextBtn.setAttribute('title', `Step ${currentIndex + 2}: ${nextTut.title}`);
      nextBtn.innerHTML = `Next: Step ${currentIndex + 2} <span class="fa fa-arrow-circle-right" aria-hidden="true"></span>`;
      nextBtn.classList.remove('btn-finish');
    } else {
      nextBtn.href = resolveDocUrl('tutorials.html');
      nextBtn.setAttribute('title', 'Pathway Complete! Return to Tutorials Overview');
      nextBtn.innerHTML = `Finish Pathway ✓ <span class="fa fa-check-circle" aria-hidden="true"></span>`;
      nextBtn.classList.add('btn-finish');
    }

    const headNext = document.querySelector('link[rel="next"]');
    if (headNext) {
      headNext.href = nextTut ? resolveDocUrl(nextTut.url) : resolveDocUrl('tutorials.html');
      headNext.setAttribute('title', nextTut ? nextTut.title : 'Finish Pathway');
    }
  }

  function initNavigator() {
    const container = document.getElementById('tutorial-navigator-app');
    if (!container) {
      return;
    }

    const data = window.RAMBLE_TUTORIAL_DATA;
    if (!data || !data.tutorials || !data.goals) {
      container.innerHTML = `
        <div class="tn-error">
          <p><strong>Note:</strong> Tutorial pathway data is loading or not available.</p>
        </div>
      `;
      return;
    }

    const tutorials = data.tutorials;
    const goals = data.goals;

    // Restore previously selected goals or default to the first goal
    let storedGoals = getStoredSelectedGoals();
    if (storedGoals === null) {
      const defaultGoals = [Object.keys(goals)[0]];
      storeSelectedGoals(defaultGoals);
      storedGoals = defaultGoals;
    }
    let selectedGoalKeys = new Set(
      Array.isArray(storedGoals) && storedGoals.length > 0
        ? storedGoals.filter((k) => goals[k])
        : []
    );

    // Render skeleton layout
    container.innerHTML = `
      <div class="tn-container">
        <div class="tn-header">
          <h3 class="tn-title">🎯 Interactive Learning Pathway Navigator</h3>
          <p class="tn-subtitle">
            Select one or more end goals to generate a customized, step-by-step tutorial curriculum.
          </p>
        </div>

        <div class="tn-goals-section">
          <div class="tn-section-heading">
            <span class="tn-heading-text">1. Choose Your End Goals (Select one or more)</span>
            <div class="tn-goal-actions">
              <button type="button" class="tn-btn tn-btn-sm" id="tn-select-all-goals">Select All</button>
              <button type="button" class="tn-btn tn-btn-sm" id="tn-clear-goals">Clear All</button>
            </div>
          </div>
          <div class="tn-goals-list" id="tn-goals-list"></div>
        </div>

        <div class="tn-summary-bar" id="tn-summary-bar"></div>

        <div class="tn-apps-section">
          <div class="tn-section-heading">
            <span class="tn-heading-text">2. Choose Preferred Application (for multi-application tutorials)</span>
          </div>
          <p class="tn-apps-desc">
            Some tutorials (such as Scaling Studies) support multiple application workloads. Select your preferred application to follow throughout those tutorials:
          </p>
          <div class="tn-apps-grid" id="tn-apps-grid"></div>
        </div>

        <div class="tn-dry-run-section">
          <div class="tn-section-heading">
            <span class="tn-heading-text">3. Execution Mode (Dry-Run vs. Full Execution)</span>
          </div>
          <div id="tn-dry-run-pref-container"></div>
        </div>

        <div class="tn-pathway-section">
          <div class="tn-section-heading">
            <span class="tn-heading-text">4. Recommended Learning Path</span>
          </div>
          <div class="tn-pathway-list" id="tn-pathway-list"></div>
        </div>
      </div>
    `;

    const goalsList = container.querySelector('#tn-goals-list');
    const summaryBar = container.querySelector('#tn-summary-bar');
    const pathwayList = container.querySelector('#tn-pathway-list');
    const selectAllBtn = container.querySelector('#tn-select-all-goals');
    const clearBtn = container.querySelector('#tn-clear-goals');

    function renderGoals() {
      goalsList.innerHTML = Object.entries(goals)
        .map(([key, goal]) => {
          const isSelected = selectedGoalKeys.has(key);
          const icon = goal.icon || '📌';
          return `
            <div class="tn-goal-item ${isSelected ? 'selected' : ''}" data-goal-key="${key}" tabindex="0" role="checkbox" aria-checked="${isSelected}">
              <div class="tn-goal-checkbox">
                <input type="checkbox" ${isSelected ? 'checked' : ''} tabindex="-1" aria-hidden="true" />
              </div>
              <div class="tn-goal-content">
                <div class="tn-goal-header">
                  <span class="tn-goal-icon">${icon}</span>
                  <span class="tn-goal-title">${goal.title}</span>
                  <span class="tn-badge tn-badge-steps">${(goal.tutorials || []).length} steps</span>
                </div>
                <div class="tn-goal-desc">${goal.description || ''}</div>
              </div>
            </div>
          `;
        })
        .join('');
    }

    function calculatePathway() {
      return getActivePathway(Array.from(selectedGoalKeys));
    }

    function renderPathway() {
      const pathway = calculatePathway();
      const completedMap = getCompletedTutorials();
      const isDryRun = getStoredDryRun();

      // Render summary bar
      if (selectedGoalKeys.size === 0) {
        summaryBar.innerHTML = `
          <div class="tn-empty-notice">
            <span>👈 Please select at least one end goal above to see your tutorial roadmap.</span>
          </div>
        `;
        pathwayList.innerHTML = `
          <div class="tn-pathway-empty">
            <p>No goals selected. Choose what you want to achieve above to see recommended tutorials.</p>
          </div>
        `;
        return;
      }

      const totalTutorials = pathway.length;
      let totalMinutes = 0;
      let completedCount = 0;

      pathway.forEach((tut) => {
        totalMinutes += parseDurationToMinutes(getEffectiveDuration(tut, isDryRun));
        if (completedMap[tut.key]) {
          completedCount++;
        }
      });

      const percent = totalTutorials > 0 ? Math.round((completedCount / totalTutorials) * 100) : 0;

      summaryBar.innerHTML = `
        <div class="tn-summary-content">
          <div class="tn-summary-metrics">
            <span class="tn-metric"><strong>${selectedGoalKeys.size}</strong> goal${selectedGoalKeys.size > 1 ? 's' : ''} selected</span>
            <span class="tn-metric-dot">•</span>
            <span class="tn-metric"><strong>${totalTutorials}</strong> tutorial${totalTutorials > 1 ? 's' : ''} total</span>
            <span class="tn-metric-dot">•</span>
            <span class="tn-metric">Estimated time: <strong>${formatMinutes(totalMinutes)}${isDryRun ? ' (dry-run)' : ''}</strong></span>
            <span class="tn-metric-dot">•</span>
            <span class="tn-metric">Progress: <strong>${completedCount}/${totalTutorials}</strong> (${percent}%)</span>
          </div>
          <div class="tn-progress-bar-bg">
            <div class="tn-progress-bar-fill" style="width: ${percent}%;"></div>
          </div>
        </div>
      `;

      // Render step-by-step pathway list
      pathwayList.innerHTML = pathway
        .map((tut, index) => {
          const isCompleted = !!completedMap[tut.key];
          const levelClass = (tut.level || 'beginner').toLowerCase();
          const effDuration = getEffectiveDuration(tut, isDryRun);
          const goalBadges = tut.requiredByGoals
            .map((gKey) => {
              const g = goals[gKey];
              return `<span class="tn-goal-tag">${g ? (g.icon ? g.icon + ' ' : '') + g.title : gKey}</span>`;
            })
            .join(' ');

          return `
            <div class="tn-step-card ${isCompleted ? 'is-completed' : ''}" data-tutorial-key="${tut.key}">
              <div class="tn-step-num-col">
                <span class="tn-step-num">Step ${index + 1}</span>
                <label class="tn-complete-toggle" title="Mark as finished">
                  <input type="checkbox" class="tn-complete-checkbox" ${isCompleted ? 'checked' : ''} />
                  <span class="tn-complete-label">Done</span>
                </label>
              </div>
              <div class="tn-step-main">
                <div class="tn-step-header">
                  <a href="${tut.url}" class="tn-step-title-link">
                    ${tut.title}
                  </a>
                  <div class="tn-step-badges">
                    <span class="tn-badge tn-badge-${levelClass}">${tut.level || 'Tutorial'}</span>
                    ${effDuration ? `<span class="tn-badge tn-badge-time">⏱️ ${effDuration}${isDryRun && tut.dry_run_duration ? ' (dry-run)' : ''}</span>` : ''}
                  </div>
                </div>
                <div class="tn-step-desc">${tut.description || ''}</div>
                <div class="tn-step-footer">
                  <div class="tn-step-goals">
                    <span class="tn-goals-label">Required for:</span>
                    ${goalBadges}
                  </div>
                  <a href="${tut.url}" class="tn-btn tn-btn-open">
                    Open Tutorial →
                  </a>
                </div>
              </div>
            </div>
          `;
        })
        .join('');

      // Attach complete toggle handlers
      pathwayList.querySelectorAll('.tn-complete-checkbox').forEach((box) => {
        box.addEventListener('change', (e) => {
          const stepCard = e.target.closest('.tn-step-card');
          const tutKey = stepCard.getAttribute('data-tutorial-key');
          setTutorialCompleted(tutKey, e.target.checked);
          renderPathway();
          updateFooterNavigation();
        });
      });
    }

    // Goal click handlers
    goalsList.addEventListener('click', (e) => {
      const item = e.target.closest('.tn-goal-item');
      if (!item) return;
      const key = item.getAttribute('data-goal-key');
      if (selectedGoalKeys.has(key)) {
        selectedGoalKeys.delete(key);
      } else {
        selectedGoalKeys.add(key);
      }
      storeSelectedGoals(Array.from(selectedGoalKeys));
      renderGoals();
      renderPathway();
      updateFooterNavigation();
    });

    goalsList.addEventListener('keydown', (e) => {
      if (e.key === ' ' || e.key === 'Enter') {
        const item = e.target.closest('.tn-goal-item');
        if (item) {
          e.preventDefault();
          item.click();
        }
      }
    });

    selectAllBtn.addEventListener('click', () => {
      selectedGoalKeys = new Set(Object.keys(goals));
      storeSelectedGoals(Array.from(selectedGoalKeys));
      renderGoals();
      renderPathway();
      updateFooterNavigation();
    });

    clearBtn.addEventListener('click', () => {
      selectedGoalKeys.clear();
      storeSelectedGoals([]);
      renderGoals();
      renderPathway();
      updateFooterNavigation();
    });

    function renderApps() {
      const apps = data.selectable_applications || {
        wrf: {
          name: 'WRF',
          workload: 'CONUS_12km',
          description: 'Weather Research and Forecasting atmospheric model'
        },
        gromacs: {
          name: 'GROMACS',
          workload: 'water_bare',
          description: 'Molecular dynamics simulation package'
        },
        hpl: {
          name: 'HPL',
          workload: 'calculator',
          description: 'High-Performance Linpack benchmark'
        }
      };

      const selectedApp = getStoredSelectedApp();
      const appsGrid = container.querySelector('#tn-apps-grid');
      if (!appsGrid) return;

      appsGrid.innerHTML = Object.entries(apps)
        .map(([key, app]) => {
          const isSelected = key === selectedApp;
          return `
            <div class="tn-app-pref-card ${isSelected ? 'active' : ''}" data-app="${key}" tabindex="0" role="radio" aria-checked="${isSelected}">
              <div class="tn-app-pref-radio">
                <input type="radio" name="tn-pref-app" value="${key}" ${isSelected ? 'checked' : ''} tabindex="-1" />
              </div>
              <div class="tn-app-pref-info">
                <div class="tn-app-pref-title-row">
                  <span class="tn-app-pref-name">${app.name || key}</span>
                  <span class="tn-badge tn-badge-time">Workload: ${app.workload || 'default'}</span>
                </div>
                <div class="tn-app-pref-desc">${app.description || ''}</div>
              </div>
            </div>
          `;
        })
        .join('');

      appsGrid.querySelectorAll('.tn-app-pref-card').forEach((card) => {
        card.addEventListener('click', () => {
          const key = card.getAttribute('data-app');
          setSelectedApp(key);
        });
        card.addEventListener('keydown', (e) => {
          if (e.key === ' ' || e.key === 'Enter') {
            e.preventDefault();
            card.click();
          }
        });
      });
    }

    function renderDryRunPref() {
      const dryRunContainer = container.querySelector('#tn-dry-run-pref-container');
      if (!dryRunContainer) return;
      const isDryRun = getStoredDryRun();
      dryRunContainer.innerHTML = `
        <div class="tn-dry-run-pref-card ${isDryRun ? 'active' : ''}" tabindex="0" role="checkbox" aria-checked="${isDryRun}">
          <div class="tn-dry-run-pref-checkbox">
            <input type="checkbox" class="tn-dry-run-checkbox" ${isDryRun ? 'checked' : ''} tabindex="-1" aria-hidden="true" />
          </div>
          <div class="tn-dry-run-pref-info">
            <div class="tn-dry-run-pref-title-row">
              <span class="tn-dry-run-pref-name">🧪 Enable Dry-Run Mode (<code>--dry-run</code>)</span>
              <span class="tn-badge tn-badge-time">⚡ Faster Walkthrough</span>
            </div>
            <div class="tn-dry-run-pref-desc">
              Runs <code>ramble workspace setup --dry-run</code> to generate experiment directories and scripts without downloading inputs or compiling software. Skips executing (<code>ramble on</code>) and analyzing (<code>ramble workspace analyze</code>) experiments, guides you through exploring the generated experiment directories, and displays example outputs for reference.
            </div>
          </div>
        </div>
      `;

      const card = dryRunContainer.querySelector('.tn-dry-run-pref-card');
      if (card) {
        card.addEventListener('click', () => {
          const nextState = !getStoredDryRun();
          setDryRun(nextState);
          renderPathway();
        });
        card.addEventListener('keydown', (e) => {
          if (e.key === ' ' || e.key === 'Enter') {
            e.preventDefault();
            card.click();
          }
        });
      }
    }

    // Hide tutorial sub-pages listing from the left sidebar if present
    const activeSidebarTutorialUl = document.querySelector('.wy-menu-vertical li.toctree-l1.current > a[href="#"] + ul');
    if (activeSidebarTutorialUl) {
      activeSidebarTutorialUl.style.display = 'none';
    }

    // Initial render
    renderGoals();
    renderApps();
    renderDryRunPref();
    renderPathway();
    updateFooterNavigation();
  }

  function initAppSwitchers() {
    const data = window.RAMBLE_TUTORIAL_DATA || {};
    const selectableApps = data.selectable_applications || {
      wrf: {
        name: 'WRF',
        workload: 'CONUS_12km',
        description: 'Weather Research and Forecasting atmospheric model'
      },
      gromacs: {
        name: 'GROMACS',
        workload: 'water_bare',
        description: 'Molecular dynamics simulation package'
      },
      hpl: {
        name: 'HPL',
        workload: 'calculator',
        description: 'High-Performance Linpack benchmark'
      }
    };

    let switchers = Array.from(document.querySelectorAll('.tn-app-switcher'));

    // If there are variants on page but no switcher, auto-insert one before the first variant
    const variants = document.querySelectorAll('.tn-app-variant, .tn-app-container');
    if (switchers.length === 0 && variants.length > 0) {
      const firstVariant = variants[0];
      const autoSwitcher = document.createElement('div');
      autoSwitcher.className = 'tn-app-switcher';
      firstVariant.parentNode.insertBefore(autoSwitcher, firstVariant);
      switchers.push(autoSwitcher);
    }

    const currentApp = getStoredSelectedApp();

    switchers.forEach((switcher) => {
      let apps = selectableApps;
      const recipeId = switcher.getAttribute('data-recipe');
      if (recipeId && data.recipes && data.recipes[recipeId] && data.recipes[recipeId].apps) {
        apps = data.recipes[recipeId].apps;
      }

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

      switcher.querySelectorAll('.tn-app-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
          const app = btn.getAttribute('data-app');
          setSelectedApp(app);
        });
      });
    });

    updateAppVariants(currentApp);
  }

  function getTutorialWorkspaceInfo(tutKey, selectedApp) {
    const data = window.RAMBLE_TUTORIAL_DATA;
    if (!data || !data.tutorials || !tutKey || !data.tutorials[tutKey]) {
      return null;
    }
    const tut = data.tutorials[tutKey];
    const defaultTemplate = tut.default_workspace_name;
    if (!defaultTemplate) {
      return null;
    }

    const app = selectedApp || getStoredSelectedApp();
    const resolvedDefault = defaultTemplate.replace('{app}', app);

    let storedCustom = null;
    try {
      storedCustom = localStorage.getItem(WS_NAME_STORAGE_PREFIX + tutKey);
      if (!storedCustom && defaultTemplate === 'tutorial-workspace-{app}') {
        storedCustom = localStorage.getItem(GLOBAL_WS_NAME_KEY);
      }
    } catch (e) {
      // ignore
    }

    if (
      storedCustom &&
      (storedCustom.trim() === resolvedDefault ||
        storedCustom.trim() === defaultTemplate ||
        storedCustom.trim() === 'tutorial-workspace')
    ) {
      storedCustom = null;
    }

    let currentName = resolvedDefault;
    let isCustom = false;
    let rawCustom = null;
    if (storedCustom && storedCustom.trim() !== '') {
      rawCustom = storedCustom.trim();
      currentName = rawCustom.replace('{app}', app);
      isCustom = currentName !== resolvedDefault;
    }

    return {
      tutKey,
      defaultTemplate,
      resolvedDefault,
      currentName,
      isCustom,
      rawCustom,
    };
  }

  function setTutorialWorkspaceName(tutKey, newName) {
    try {
      const activeApp = getStoredSelectedApp();
      const info = getTutorialWorkspaceInfo(tutKey, activeApp);
      if (!info) return;
      const trimmed = (newName || '').trim();
      const isDefault =
        !trimmed ||
        trimmed === info.resolvedDefault ||
        trimmed === info.defaultTemplate ||
        trimmed === 'tutorial-workspace';

      if (isDefault) {
        if (info.defaultTemplate === 'tutorial-workspace-{app}') {
          localStorage.removeItem(GLOBAL_WS_NAME_KEY);
        }
        localStorage.removeItem(WS_NAME_STORAGE_PREFIX + tutKey);
        const data = window.RAMBLE_TUTORIAL_DATA;
        if (data && data.tutorials) {
          Object.keys(data.tutorials).forEach((k) => {
            if (data.tutorials[k].default_workspace_name === info.defaultTemplate) {
              localStorage.removeItem(WS_NAME_STORAGE_PREFIX + k);
            }
          });
        }
      } else {
        if (info.defaultTemplate === 'tutorial-workspace-{app}') {
          localStorage.setItem(GLOBAL_WS_NAME_KEY, trimmed);
        }
        localStorage.setItem(WS_NAME_STORAGE_PREFIX + tutKey, trimmed);
        const data = window.RAMBLE_TUTORIAL_DATA;
        if (data && data.tutorials) {
          Object.keys(data.tutorials).forEach((k) => {
            if (data.tutorials[k].default_workspace_name === info.defaultTemplate) {
              localStorage.setItem(WS_NAME_STORAGE_PREFIX + k, trimmed);
            }
          });
        }
      }
    } catch (e) {
      console.warn('Could not save custom workspace name:', e);
    }
  }

  function tagWorkspaceNames(rootContainer, candidateNames) {
    if (!rootContainer || candidateNames.length === 0) return;

    // Filter candidate names to ensure valid non-empty strings
    const validCandidates = Array.from(new Set(candidateNames.filter((n) => typeof n === 'string' && n.length > 0)));
    if (validCandidates.length === 0) return;

    // Sort descending by length so longer names match first
    validCandidates.sort((a, b) => b.length - a.length);

    // Escape regex characters
    const escaped = validCandidates.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    const pattern = new RegExp(`(?<![a-zA-Z0-9_.-])(${escaped.join('|')})(?![a-zA-Z0-9_.-])`, 'g');

    const walker = document.createTreeWalker(rootContainer, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const parent = node.parentNode;
        if (!parent) return NodeFilter.FILTER_REJECT;
        const tag = parent.nodeName.toUpperCase();
        if (['SCRIPT', 'STYLE', 'BUTTON', 'INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) {
          return NodeFilter.FILTER_REJECT;
        }
        if (
          parent.closest &&
          (parent.closest('.tn-ws-prompt-card') ||
            parent.closest('.tn-ws-prompt-row') ||
            parent.closest('.tn-dry-run-row') ||
            parent.closest('.tn-ws-name'))
        ) {
          return NodeFilter.FILTER_REJECT;
        }
        return pattern.test(node.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
      },
    });

    const textNodes = [];
    while (walker.nextNode()) {
      textNodes.push(walker.currentNode);
    }

    textNodes.forEach((node) => {
      const text = node.nodeValue;
      pattern.lastIndex = 0;
      let match;
      let lastIdx = 0;
      const frag = document.createDocumentFragment();

      while ((match = pattern.exec(text)) !== null) {
        if (match.index > lastIdx) {
          frag.appendChild(document.createTextNode(text.substring(lastIdx, match.index)));
        }
        const span = document.createElement('span');
        span.className = 'tn-ws-name';
        span.setAttribute('data-default', match[1]);
        span.textContent = match[1];
        frag.appendChild(span);
        lastIdx = pattern.lastIndex;
      }

      if (lastIdx < text.length) {
        frag.appendChild(document.createTextNode(text.substring(lastIdx)));
      }

      if (node.parentNode) {
        node.parentNode.replaceChild(frag, node);
      }
    });
  }

  function applyWorkspaceNameToSpans(currentName, isCustom) {
    document.querySelectorAll('.tn-ws-name').forEach((span) => {
      span.textContent = currentName;
      if (isCustom) {
        span.classList.add('is-custom');
      } else {
        span.classList.remove('is-custom');
      }
    });
  }

  function updateWorkspacePromptControls(info) {
    document.querySelectorAll('.tn-ws-input').forEach((input) => {
      input.value = info.isCustom ? (info.rawCustom || info.currentName) : info.currentName;
      input.placeholder = info.resolvedDefault;
      if (info.isCustom) {
        input.classList.add('is-custom');
      } else {
        input.classList.remove('is-custom');
      }
    });

    document.querySelectorAll('.tn-ws-reset-btn').forEach((btn) => {
      btn.style.display = info.isCustom ? 'inline-flex' : 'none';
    });
  }

  function initWorkspaceName() {
    const tutKey = getCurrentTutorialKey();
    if (!tutKey) return;

    const data = window.RAMBLE_TUTORIAL_DATA;
    const tut = data && data.tutorials ? data.tutorials[tutKey] : null;
    if (!tut || !tut.default_workspace_name) return;

    // 1. Gather all candidate default names that might appear in text nodes for this tutorial
    const template = tut.default_workspace_name;
    const candidateNames = new Set();
    if (template.includes('{app}')) {
      candidateNames.add('tutorial-workspace');
      const selectableApps = data.selectable_applications || { wrf: {}, gromacs: {}, hpl: {} };
      const legacyPrefixes = [
        'basic',
        'vectors',
        'software',
        'scaling',
        'success',
        'modifiers',
        'zips',
        'var_expansion',
        'internals',
      ];
      Object.keys(selectableApps).forEach((app) => {
        candidateNames.add(template.replace('{app}', app));
        legacyPrefixes.forEach((prefix) => {
          candidateNames.add(`${prefix}_${app}`);
        });
      });
    } else {
      candidateNames.add(template);
    }

    const currentApp = getStoredSelectedApp();
    const info = getTutorialWorkspaceInfo(tutKey, currentApp);
    if (!info) return;

    if (info.isCustom) {
      candidateNames.add(info.currentName);
    }

    // 2. Tag text nodes in the article container
    const articleContainer = document.querySelector('div[itemprop="articleBody"]') ||
      document.querySelector('.document') ||
      document.body;
    tagWorkspaceNames(articleContainer, Array.from(candidateNames));

    // 3. Inject interactive prompt control
    const displayValue = info.isCustom ? (info.rawCustom || info.currentName) : info.currentName;

    const appSwitcherCard = document.querySelector('.tn-app-switcher-card');
    if (appSwitcherCard) {
      if (!appSwitcherCard.querySelector('.tn-ws-prompt-row')) {
        const row = document.createElement('div');
        row.className = 'tn-ws-prompt-row';
        row.innerHTML = `
          <label class="tn-ws-prompt-label" for="tn-ws-name-input">
            📁 Workspace Name:
          </label>
          <div class="tn-ws-input-wrap">
            <input type="text" id="tn-ws-name-input" class="tn-ws-input" value="${displayValue}" placeholder="${info.resolvedDefault}" spellcheck="false" autocomplete="off" />
          </div>
          <button type="button" class="tn-ws-reset-btn" id="tn-ws-reset-btn" title="Reset workspace name to default" style="display: ${info.isCustom ? 'inline-flex' : 'none'};">
            ↺ Reset to Default
          </button>
          <div class="tn-ws-prompt-help">
            Customizing this updates commands, paths, and configs in this tutorial in real time.
          </div>
        `;
        appSwitcherCard.appendChild(row);
      }
    } else {
      let promptTarget = document.querySelector('.tn-ws-prompt');
      if (!promptTarget) {
        // Find the first highlight console block that contains 'workspace create' or the first code block
        const codeBlocks = document.querySelectorAll('.highlight-console, .highlight-bash, .highlight');
        for (const block of codeBlocks) {
          if (block.textContent.includes('workspace create') || block.textContent.includes('workspace')) {
            promptTarget = block;
            break;
          }
        }
        if (!promptTarget && codeBlocks.length > 0) {
          promptTarget = codeBlocks[0];
        }
      }

      if (promptTarget && !document.querySelector('.tn-ws-prompt-card')) {
        const card = document.createElement('div');
        card.className = 'tn-ws-prompt-card';
        card.innerHTML = `
          <div class="tn-ws-prompt-row">
            <label class="tn-ws-prompt-label" for="tn-ws-name-input">
              📁 Workspace Name:
            </label>
            <div class="tn-ws-input-wrap">
              <input type="text" id="tn-ws-name-input" class="tn-ws-input" value="${displayValue}" placeholder="${info.resolvedDefault}" spellcheck="false" autocomplete="off" />
            </div>
            <button type="button" class="tn-ws-reset-btn" id="tn-ws-reset-btn" title="Reset workspace name to default" style="display: ${info.isCustom ? 'inline-flex' : 'none'};">
              ↺ Reset to Default
            </button>
            <div class="tn-ws-prompt-help">
              Customize the workspace name to update commands, paths, and examples in this tutorial.
            </div>
          </div>
        `;
        promptTarget.parentNode.insertBefore(card, promptTarget);
      }
    }

    // 4. Attach event listeners
    document.querySelectorAll('.tn-ws-input').forEach((input) => {
      input.addEventListener('input', (e) => {
        const val = e.target.value.trim();
        const activeApp = getStoredSelectedApp();
        const curInfo = getTutorialWorkspaceInfo(tutKey, activeApp);
        const nameToUse = val.length > 0 ? val.replace('{app}', activeApp) : curInfo.resolvedDefault;
        setTutorialWorkspaceName(
          tutKey,
          val.length > 0 && val !== curInfo.resolvedDefault && val !== curInfo.defaultTemplate
            ? val
            : null
        );

        const updatedInfo = getTutorialWorkspaceInfo(tutKey, activeApp);
        document.querySelectorAll('.tn-ws-input').forEach((otherInput) => {
          if (otherInput !== input) {
            otherInput.value = e.target.value;
          }
          otherInput.placeholder = updatedInfo.resolvedDefault;
          if (updatedInfo.isCustom) {
            otherInput.classList.add('is-custom');
          } else {
            otherInput.classList.remove('is-custom');
          }
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
        const activeApp = getStoredSelectedApp();
        setTutorialWorkspaceName(tutKey, null);
        const updatedInfo = getTutorialWorkspaceInfo(tutKey, activeApp);
        updateWorkspacePromptControls(updatedInfo);
        applyWorkspaceNameToSpans(updatedInfo.resolvedDefault, false);
        initWorkspaceLifecycle();
      });
    });

    // 5. Initial application to spans
    applyWorkspaceNameToSpans(info.currentName, info.isCustom);
    updateWorkspacePromptControls(info);
  }

  function initDryRunControls() {
    const isDryRun = getStoredDryRun();
    updateDryRunMode(isDryRun);

    const tutKey = getCurrentTutorialKey();
    if (!tutKey) return;

    const data = window.RAMBLE_TUTORIAL_DATA;
    const tut = data && data.tutorials ? data.tutorials[tutKey] : null;
    const hasDryRunBlocks = document.querySelector('.tn-dry-run-only, .tn-full-run-only') !== null;

    if ((!tut || !tut.dry_run_duration) && !hasDryRunBlocks) {
      return;
    }

    let hostCard =
      document.querySelector('.tn-app-switcher-card') ||
      document.querySelector('.tn-ws-prompt-card');

    if (!hostCard) {
      const firstBlock = document.querySelector('.tn-dry-run-only, .tn-full-run-only, .highlight-console');
      if (firstBlock && firstBlock.parentNode) {
        hostCard = document.createElement('div');
        hostCard.className = 'tn-ws-prompt-card';
        firstBlock.parentNode.insertBefore(hostCard, firstBlock);
      }
    }

    if (!hostCard || hostCard.querySelector('.tn-dry-run-row')) {
      return;
    }

    const effDuration = getEffectiveDuration(tut, isDryRun);
    const row = document.createElement('div');
    row.className = 'tn-dry-run-row';
    row.innerHTML = `
      <label class="tn-dry-run-toggle">
        <input type="checkbox" class="tn-dry-run-checkbox" ${isDryRun ? 'checked' : ''} />
        <span>🧪 Enable Dry-Run Mode (<code>--dry-run</code>)</span>
      </label>
      ${
        effDuration
          ? `<span class="tn-tut-duration-badge">⏱️ Estimated Time: ${effDuration}${isDryRun && tut && tut.dry_run_duration ? ' (dry-run)' : ''}</span>`
          : ''
      }
      <div class="tn-dry-run-help">
        Runs <code>ramble workspace setup --dry-run</code>, skips executing (<code>ramble on</code>) and analyzing (<code>ramble workspace analyze</code>) experiments, and guides you through inspecting the generated experiment directories while showing example outputs for reference.
      </div>
    `;
    hostCard.appendChild(row);

    const checkbox = row.querySelector('.tn-dry-run-checkbox');
    if (checkbox) {
      checkbox.addEventListener('change', (e) => {
        setDryRun(e.target.checked);
      });
    }
  }

  function wrapOriginalContent(targetEl, noticeHtml, modifierClass) {
    if (!targetEl) return;

    let fallbackDetails = targetEl.querySelector('.tn-standalone-fallback');

    if (!fallbackDetails) {
      const heading = targetEl.querySelector('h1, h2, h3, h4, h5, h6');
      const nodesToWrap = [];
      Array.from(targetEl.childNodes).forEach((node) => {
        if (node === heading) return;
        if (
          node.nodeType === Node.ELEMENT_NODE &&
          node.classList &&
          (node.classList.contains('tn-lifecycle-notice') || node.classList.contains('tn-standalone-fallback'))
        ) {
          return;
        }
        nodesToWrap.push(node);
      });

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
      noticeEl.className = `tn-lifecycle-notice ${modifierClass || ''}`;
      if (fallbackDetails) {
        targetEl.insertBefore(noticeEl, fallbackDetails);
      } else {
        targetEl.appendChild(noticeEl);
      }
    } else {
      noticeEl.className = `tn-lifecycle-notice ${modifierClass || ''}`;
    }

    noticeEl.innerHTML = noticeHtml;
  }

  function unwrapOriginalContent(targetEl) {
    if (!targetEl) return;
    const noticeEl = targetEl.querySelector('.tn-lifecycle-notice');
    if (noticeEl) {
      noticeEl.remove();
    }
    const fallbackDetails = targetEl.querySelector('.tn-standalone-fallback');
    if (fallbackDetails) {
      const contentDiv = fallbackDetails.querySelector('.tn-standalone-content');
      if (contentDiv) {
        while (contentDiv.firstChild) {
          targetEl.insertBefore(contentDiv.firstChild, fallbackDetails);
        }
      }
      fallbackDetails.remove();
    }
  }

  function findWorkspaceCreateElements() {
    const elements = Array.from(document.querySelectorAll('.tn-workspace-create'));
    if (elements.length > 0) return elements;

    const sections = document.querySelectorAll('section, div.section');
    for (const sec of sections) {
      const heading = sec.querySelector('h1, h2, h3, h4, h5, h6');
      const headingText = heading ? heading.textContent.replace(/[\uF0C1\u00B6#\s]+$/, '').trim() : '';
      const id = sec.id || '';
      if (
        /^(creat(e|ing)|activate)(\s+and\s+activate)?(\s+(a|the))?\s+workspace$/i.test(headingText) ||
        ((id.includes('create') || id.includes('activate')) && id.includes('workspace'))
      ) {
        return [sec];
      }
    }
    return [];
  }

  function findWorkspaceCleanupElements() {
    const elements = Array.from(document.querySelectorAll('.tn-workspace-cleanup'));
    if (elements.length > 0) return elements;

    const sections = document.querySelectorAll('section, div.section');
    for (const sec of sections) {
      const heading = sec.querySelector('h1, h2, h3, h4, h5, h6');
      const headingText = heading ? heading.textContent.replace(/[\uF0C1\u00B6#\s]+$/, '').trim() : '';
      const id = sec.id || '';
      if (
        /^(clean(\s*up|ing)?\s+(the\s+|a\s+)?workspace|conclusion\s+and\s+cleanup|summary\s+and\s+final\s+cleanup|cleanup)$/i.test(headingText) ||
        ((id.includes('clean') || id.includes('cleanup') || id.includes('remove')) && (id.includes('workspace') || id.includes('cleanup')))
      ) {
        return [sec];
      }
    }
    return [];
  }

  function handleWorkspaceCreateLifecycle(pathway, currentIndex, info) {
    if (!info) return;
    const createEls = findWorkspaceCreateElements();
    if (createEls.length === 0) return;

    const currentName = info.currentName;
    const currentApp = getStoredSelectedApp();

    // Check if an earlier tutorial in the pathway used/created this workspace
    let isReusedFromEarlier = false;
    const curStep = pathway[currentIndex];
    if (curStep) {
      if (curStep.reuses_workspace_from) {
        const prevIndex = pathway.findIndex((t) => t.key === curStep.reuses_workspace_from);
        if (prevIndex !== -1 && prevIndex < currentIndex) {
          isReusedFromEarlier = true;
        }
      }
      if (!isReusedFromEarlier && !curStep.workspace_dir_mode) {
        isReusedFromEarlier = pathway.slice(0, currentIndex).some((t) => {
          const prevInfo = getTutorialWorkspaceInfo(t.key, currentApp);
          return (
            !t.workspace_dir_mode &&
            prevInfo &&
            prevInfo.currentName === currentName &&
            t.default_workspace_name === curStep.default_workspace_name
          );
        });
      }
    }

    createEls.forEach((el) => {
      if (isReusedFromEarlier) {
        // Workspace was already created in an earlier step! Turn into hypothetical create + actionable activate.
        const isDirMode = Boolean(curStep && curStep.workspace_dir_mode);
        const createCmd = isDirMode
          ? `$ ramble workspace create -d <span class="tn-ws-name">${currentName}</span>`
          : `$ ramble workspace create <span class="tn-ws-name">${currentName}</span>`;
        const activateCmd = isDirMode
          ? `$ ramble workspace activate -d <span class="tn-ws-name">${currentName}</span>`
          : `$ ramble workspace activate <span class="tn-ws-name">${currentName}</span>`;
        const removeCmd = isDirMode
          ? `$ rm -rf <span class="tn-ws-name">${currentName}</span>`
          : `$ ramble workspace remove <span class="tn-ws-name">${currentName}</span>`;

        const cleanNote =
          curStep && curStep.key === 'modify_experiment'
            ? '<p><em>Note: This tutorial modifies the experiment configured in Creating a Single Experiment Workspace, so if you start clean you will need to re-add that experiment first.</em></p>'
            : '';

        const noticeHtml = `
          <div class="tn-lifecycle-header">
            <span class="tn-lifecycle-badge">Active Learning Path</span>
            <span>Workspace Already Configured</span>
          </div>
          <div class="tn-lifecycle-body">
            <p>In a standalone scenario where you started directly with this tutorial, you would create and configure a new workspace from scratch:</p>
            <div class="tn-hypothetical-code">${createCmd}</div>
            <div class="tn-lifecycle-action-callout">
              <strong>✓ Workspace Ready:</strong> You already created and configured <code><span class="tn-ws-name">${currentName}</span></code> earlier in this learning path.
              <p>To continue with this tutorial, ensure the workspace is active in your current shell:</p>
              <div class="tn-actionable-code">${activateCmd}</div>
              <p>If your workspace is already active from the previous step, you can continue directly to the next section!</p>
            </div>
            <div class="tn-lifecycle-action-callout">
              <strong>🔄 Alternative — Start Clean:</strong> If you wish to remove the existing workspace first and start clean in this tutorial, run:
              <div class="tn-actionable-code">
                $ ramble workspace deactivate<br />
                ${removeCmd}<br />
                ${createCmd}<br />
                ${activateCmd}
              </div>
              ${cleanNote}
            </div>
          </div>
        `;
        wrapOriginalContent(el, noticeHtml, 'notice-reuse');
      } else {
        unwrapOriginalContent(el);
      }
    });
  }

  function handleWorkspaceCleanupLifecycle(pathway, currentIndex, info) {
    if (!info) return;
    const cleanupEls = findWorkspaceCleanupElements();
    if (cleanupEls.length === 0) return;

    const data = window.RAMBLE_TUTORIAL_DATA;
    const currentName = info.currentName;
    const currentApp = getStoredSelectedApp();
    const hasFutureWorkspaceStep = pathway
      .slice(currentIndex + 1)
      .some((t) => Boolean(t.default_workspace_name));
    const isFinalStep = currentIndex === pathway.length - 1 || !hasFutureWorkspaceStep;
    const curStep = pathway[currentIndex];
    const isDirMode = Boolean(curStep && curStep.workspace_dir_mode);

    const goalNames = (curStep.requiredByGoals || [])
      .map((gKey) => (data && data.goals && data.goals[gKey] ? data.goals[gKey].title : gKey))
      .join(', ');

    cleanupEls.forEach((el) => {
      if (isFinalStep) {
        // Final step: consolidated cleanup of all unique workspaces across the pathway
        const uniqueWorkspaces = [];
        const seenWs = new Set();
        pathway.forEach((step) => {
          const sInfo = getTutorialWorkspaceInfo(step.key, currentApp);
          const stepDirMode = Boolean(step.workspace_dir_mode);
          const wsKey = sInfo && sInfo.currentName ? `${stepDirMode ? 'dir:' : 'named:'}${sInfo.currentName}` : null;
          if (wsKey && !seenWs.has(wsKey)) {
            seenWs.add(wsKey);
            uniqueWorkspaces.push({
              name: sInfo.currentName,
              dirMode: stepDirMode,
              isMultiWsConfig: step.key === 'workspace_config_cmd',
            });
          }
        });

        const removeCommands = uniqueWorkspaces
          .map((ws) => {
            if (ws.isMultiWsConfig) {
              return `$ rm -rf <strong>${ws.name} squash-workspace</strong>`;
            }
            return ws.dirMode
              ? `$ rm -rf <strong>${ws.name}</strong>`
              : `$ ramble workspace remove <strong>${ws.name}</strong>`;
          })
          .join('<br />');

        const noticeHtml = `
          <div class="tn-lifecycle-header">
            <span class="tn-lifecycle-badge">Pathway Complete</span>
            <span>🎉 Consolidated Workspace Cleanup</span>
          </div>
          <div class="tn-lifecycle-body">
            <p>Congratulations on completing the <strong>${goalNames || 'recommended'}</strong> learning path! Now that you have finished all workspace exercises, you can clean up all workspaces created during your journey:</p>
            <div class="tn-actionable-code">
              $ ramble workspace deactivate<br />
              ${removeCommands}
            </div>
            <p>If you wish to retain your experiment configurations or generated results for future exploration, you can safely skip the workspace removal command above.</p>
          </div>
        `;
        wrapOriginalContent(el, noticeHtml, 'notice-consolidated');
      } else {
        // Intermediate step: hypothetical cleanup discussion
        const futureReused = pathway.slice(currentIndex + 1).some((t) => {
          if (t.reuses_workspace_from === curStep.key) return true;
          const futureInfo = getTutorialWorkspaceInfo(t.key, currentApp);
          return (
            !isDirMode &&
            !t.workspace_dir_mode &&
            futureInfo &&
            futureInfo.currentName === currentName &&
            t.default_workspace_name === curStep.default_workspace_name
          );
        });

        const singleRemoveCmd = isDirMode
          ? `$ rm -rf <span class="tn-ws-name">${currentName}</span>`
          : `$ ramble workspace remove <span class="tn-ws-name">${currentName}</span>`;

        let noticeHtml;
        if (futureReused) {
          noticeHtml = `
            <div class="tn-lifecycle-header">
              <span class="tn-lifecycle-badge">Active Learning Path</span>
              <span>Keep Workspace Active for Next Steps</span>
            </div>
            <div class="tn-lifecycle-body">
              <p>In a standalone scenario where you are not following a multi-step pathway, you would clean up by deactivating and removing the workspace at this point:</p>
              <div class="tn-hypothetical-code">
                $ ramble workspace deactivate<br />
                ${singleRemoveCmd}
              </div>
              <div class="tn-lifecycle-action-callout">
                <strong>⚠️ Pathway Action: Do NOT remove this workspace yet!</strong>
                <p>Because you are following the <strong>${goalNames || 'Active'}</strong> learning path, subsequent tutorial content builds directly upon this workspace. Keep <code><span class="tn-ws-name">${currentName}</span></code> intact and proceed to the next tutorial.</p>
                <p>A consolidated workspace cleanup will be provided at the end of your learning path.</p>
              </div>
            </div>
          `;
        } else {
          noticeHtml = `
            <div class="tn-lifecycle-header">
              <span class="tn-lifecycle-badge">Active Learning Path</span>
              <span>Keep Workspace Active Until Pathway Completion</span>
            </div>
            <div class="tn-lifecycle-body">
              <p>In a standalone scenario, you would remove this workspace once finished:</p>
              <div class="tn-hypothetical-code">
                $ ramble workspace deactivate<br />
                ${singleRemoveCmd}
              </div>
              <div class="tn-lifecycle-action-callout">
                <strong>💡 Pathway Notice:</strong> You can leave this workspace in place and continue along your learning path. All workspaces created along this pathway will be cleaned up together at the end of the learning path.
              </div>
            </div>
          `;
        }
        wrapOriginalContent(el, noticeHtml, 'notice-hypothetical');
      }
    });
  }

  function findRepoCreateElements() {
    return Array.from(document.querySelectorAll('.tn-repo-create'));
  }

  function findRepoCleanupElements() {
    return Array.from(document.querySelectorAll('.tn-repo-cleanup'));
  }

  function handleRepoCreateLifecycle(pathway, currentIndex) {
    const createEls = findRepoCreateElements();
    if (createEls.length === 0) return;

    const curStep = pathway[currentIndex];
    const repoName = curStep && curStep.default_repo_name;
    if (!repoName) {
      createEls.forEach((el) => unwrapOriginalContent(el));
      return;
    }

    let isReusedFromEarlier = false;
    if (curStep.reuses_repo_from) {
      const prevIndex = pathway.findIndex((t) => t.key === curStep.reuses_repo_from);
      if (prevIndex !== -1 && prevIndex < currentIndex) {
        isReusedFromEarlier = true;
      }
    }
    if (!isReusedFromEarlier) {
      isReusedFromEarlier = pathway
        .slice(0, currentIndex)
        .some((t) => t.default_repo_name && t.default_repo_name === repoName);
    }

    createEls.forEach((el) => {
      if (isReusedFromEarlier) {
        const noticeHtml = `
          <div class="tn-lifecycle-header">
            <span class="tn-lifecycle-badge">Active Learning Path</span>
            <span>Repository Already Configured</span>
          </div>
          <div class="tn-lifecycle-body">
            <p>In a standalone scenario where you started directly with this tutorial, you would create and register a new object repository from scratch:</p>
            <div class="tn-hypothetical-code">
              $ ramble repo create ${repoName}<br />
              $ ramble repo add ${repoName}
            </div>
            <div class="tn-lifecycle-action-callout">
              <strong>✓ Repository Ready:</strong> You already created and registered <code>${repoName}</code> earlier in this learning path.
              <p>You can verify that it is still registered in your environment with:</p>
              <div class="tn-actionable-code">$ ramble repo list</div>
              <p>If <code>${repoName}</code> is already registered from the previous step, you can continue directly to the next section!</p>
            </div>
            <div class="tn-lifecycle-action-callout">
              <strong>🔄 Alternative — Start Clean:</strong> If you wish to remove the existing repository first and start clean in this tutorial, run:
              <div class="tn-actionable-code">
                $ ramble repo rm ${repoName}<br />
                $ rm -rf ${repoName}<br />
                $ ramble repo create ${repoName}<br />
                $ ramble repo add ${repoName}
              </div>
            </div>
          </div>
        `;
        wrapOriginalContent(el, noticeHtml, 'notice-reuse');
      } else {
        unwrapOriginalContent(el);
      }
    });
  }

  function handleRepoCleanupLifecycle(pathway, currentIndex) {
    const cleanupEls = findRepoCleanupElements();
    if (cleanupEls.length === 0) return;

    const data = window.RAMBLE_TUTORIAL_DATA;
    const curStep = pathway[currentIndex];
    const repoName = (curStep && curStep.default_repo_name) || 'tutorial-repo';

    const futureRepoSteps = pathway
      .slice(currentIndex + 1)
      .filter((t) => Boolean(t.default_repo_name));
    const isFinalRepoStep = futureRepoSteps.length === 0;

    const goalNames = ((curStep && curStep.requiredByGoals) || [])
      .map((gKey) => (data && data.goals && data.goals[gKey] ? data.goals[gKey].title : gKey))
      .join(', ');

    cleanupEls.forEach((el) => {
      if (isFinalRepoStep) {
        const uniqueRepos = [];
        const seenRepos = new Set();
        pathway.forEach((step) => {
          if (step.default_repo_name && !seenRepos.has(step.default_repo_name)) {
            seenRepos.add(step.default_repo_name);
            uniqueRepos.push(step.default_repo_name);
          }
        });
        if (uniqueRepos.length === 0) {
          uniqueRepos.push(repoName);
        }

        const removeRepoCommands = uniqueRepos
          .map(
            (rName) =>
              `$ ramble repo rm <strong>${rName}</strong><br />$ rm -rf <strong>${rName}</strong>`
          )
          .join('<br />');

        const noticeHtml = `
          <div class="tn-lifecycle-header">
            <span class="tn-lifecycle-badge">Pathway Complete</span>
            <span>🎉 Consolidated Repository Cleanup</span>
          </div>
          <div class="tn-lifecycle-body">
            <p>Now that you have finished all repository exercises in the <strong>${goalNames || 'recommended'}</strong> learning path, you can unregister and remove the custom repository created during your journey:</p>
            <div class="tn-actionable-code">
              ${removeRepoCommands}
            </div>
            <p>If you wish to retain your custom object definitions for future use, you can safely skip the repository removal commands above.</p>
          </div>
        `;
        wrapOriginalContent(el, noticeHtml, 'notice-consolidated');
      } else {
        const noticeHtml = `
          <div class="tn-lifecycle-header">
            <span class="tn-lifecycle-badge">Active Learning Path</span>
            <span>Keep Repository Registered for Next Steps</span>
          </div>
          <div class="tn-lifecycle-body">
            <p>In a standalone scenario where you are not following a multi-step pathway, you would clean up by unregistering and removing the repository at this point:</p>
            <div class="tn-hypothetical-code">
              $ ramble repo rm ${repoName}<br />
              $ rm -rf ${repoName}
            </div>
            <div class="tn-lifecycle-action-callout">
              <strong>⚠️ Pathway Action: Do NOT remove this repository yet!</strong>
              <p>Because you are following the <strong>${goalNames || 'Active'}</strong> learning path, subsequent tutorials will also use the <code>${repoName}</code> repository. Keep <code>${repoName}</code> registered and proceed to the next tutorial.</p>
              <p>A consolidated repository cleanup will be provided at the end of your learning path.</p>
            </div>
          </div>
        `;
        wrapOriginalContent(el, noticeHtml, 'notice-hypothetical');
      }
    });
  }

  function initWorkspaceLifecycle() {
    const tutKey = getCurrentTutorialKey();
    if (!tutKey) return;

    const data = window.RAMBLE_TUTORIAL_DATA;
    if (!data || !data.tutorials) return;

    const pathway = getActivePathway();
    const currentIndex = pathway.findIndex((t) => t.key === tutKey);
    if (currentIndex === -1) {
      const createEls = findWorkspaceCreateElements();
      createEls.forEach((el) => unwrapOriginalContent(el));
      const cleanupEls = findWorkspaceCleanupElements();
      cleanupEls.forEach((el) => unwrapOriginalContent(el));
      const repoCreateEls = findRepoCreateElements();
      repoCreateEls.forEach((el) => unwrapOriginalContent(el));
      const repoCleanupEls = findRepoCleanupElements();
      repoCleanupEls.forEach((el) => unwrapOriginalContent(el));
      return;
    }

    handleRepoCreateLifecycle(pathway, currentIndex);
    handleRepoCleanupLifecycle(pathway, currentIndex);

    const currentApp = getStoredSelectedApp();
    const info = getTutorialWorkspaceInfo(tutKey, currentApp);
    if (!info) return;

    handleWorkspaceCreateLifecycle(pathway, currentIndex, info);
    handleWorkspaceCleanupLifecycle(pathway, currentIndex, info);

    applyWorkspaceNameToSpans(info.currentName, info.isCustom);
  }

  window.addEventListener('storage', (e) => {
    if (e.key === APP_STORAGE_KEY) {
      updateAppVariants(e.newValue || DEFAULT_APP);
    }
    if (e.key === DRY_RUN_STORAGE_KEY) {
      updateDryRunMode(e.newValue === 'true');
      if (isTutorialsOverviewPage()) {
        initNavigator();
      }
    }
    if (e.key === GOALS_STORAGE_KEY || e.key === STORAGE_KEY) {
      updateFooterNavigation();
      initWorkspaceLifecycle();
    }
    if (e.key === GLOBAL_WS_NAME_KEY || (e.key && e.key.startsWith(WS_NAME_STORAGE_PREFIX))) {
      const tutKey = getCurrentTutorialKey();
      if (tutKey) {
        const info = getTutorialWorkspaceInfo(tutKey);
        if (info) {
          updateWorkspacePromptControls(info);
          applyWorkspaceNameToSpans(info.currentName, info.isCustom);
          initWorkspaceLifecycle();
        }
      }
    }
  });

  function initializeAll() {
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
