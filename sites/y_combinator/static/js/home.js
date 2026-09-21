/* Native scroll, media and pointer APIs reproduce the captured homepage.
   No network services, animation package or runtime source JSON is required. */
(() => {
  const home = document.querySelector('.homepage');
  if (!home) return;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const desktop = matchMedia('(min-width: 1024px)');
  const touch = matchMedia('(hover: none)');
  const band = home.querySelector('.reveal');
  const names = [...home.querySelectorAll('[data-story-index]')];
  const frames = [...home.querySelectorAll('[data-story-frame]')];
  const logoGroups = [...home.querySelectorAll('.story-logos')];
  const hero = home.querySelector('.hero > .shell');
  let queued = false;

  function updateBand() {
    queued = false;
    const height = innerHeight;
    hero.style.opacity = desktop.matches && !reduced.matches ? Math.max(0, 1 - scrollY / 400) : 1;
    let active = -1;
    let distance = Infinity;
    let progress = 0;
    if (desktop.matches && band) {
      const section = band.getBoundingClientRect();
      if (section.bottom > 0 && section.top < height) {
        names.forEach((name, index) => {
          const rect = name.getBoundingClientRect();
          const delta = Math.abs(rect.top + rect.height / 2 - height * .56);
          if (delta < distance) { distance = delta; active = index; }
        });
        if (distance > height * .15) active = -1;
        const total = names.at(-1).getBoundingClientRect();
        const delta = height / 2 - (total.top + total.height / 2);
        progress = delta < -height * .17 ? 0 : delta < 0 ? (delta + height * .17) / (height * .17)
          : delta < height * .1 ? 1 : 1 - (delta - height * .1) / (height * .18);
        progress = Math.max(0, Math.min(1, progress));
      }
    }
    names.forEach((name, index) => {
      const selected = index === active || (index === names.length - 1 && progress > 0);
      name.classList.toggle('active', selected);
      name.setAttribute('aria-pressed', String(selected));
    });
    frames.forEach(frame => {
      const visible = Number(frame.dataset.storyFrame) === active;
      frame.classList.toggle('active', visible);
      frame.setAttribute('aria-hidden', String(!visible));
    });
    logoGroups.forEach(group => {
      group.setAttribute('aria-hidden', String(progress === 0));
      [...group.children].forEach((logo, index) => {
        const start = index * .85 / Math.max(1, group.children.length - 1);
        logo.style.opacity = Math.max(0, Math.min(1, (progress - start) / .15));
      });
    });
  }
  function scheduleBand() {
    if (!queued) { queued = true; requestAnimationFrame(updateBand); }
  }
  names.forEach(name => name.addEventListener('click', () => {
    const rect = name.getBoundingClientRect();
    scrollBy({top: rect.top + rect.height / 2 - innerHeight * .56, behavior: reduced.matches ? 'instant' : 'smooth'});
  }));
  addEventListener('scroll', scheduleBand, {passive: true});
  addEventListener('resize', scheduleBand);
  reduced.addEventListener('change', scheduleBand);
  desktop.addEventListener('change', scheduleBand);

  const rail = home.querySelector('.mobile-stories');
  const stories = [...home.querySelectorAll('.mobile-story')];
  let storyIndex = 0;
  let storyElapsed = 0;
  let manual = false;
  let animatingUntil = 0;
  let previousTime = 0;
  let storyFrame = 0;

  function showNow(card, now) {
    card.classList.toggle('show-now', now);
    card.setAttribute('aria-pressed', String(now));
  }
  function storyVisible() {
    if (desktop.matches || document.hidden || !stories.length) return false;
    const r = stories[storyIndex].getBoundingClientRect();
    const visible = Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 64));
    return visible / r.height >= .9;
  }
  function setStory(index) {
    storyIndex = index;
    storyElapsed = 0;
    previousTime = 0;
    stories.forEach(card => {
      showNow(card, false);
      card.querySelector('.progress-young').style.width = '0%';
      card.querySelector('.progress-now').style.width = '0%';
    });
  }
  function wakeStory() {
    if (!storyFrame && !reduced.matches && storyVisible() && storyElapsed < 6000) {
      previousTime = 0;
      storyFrame = requestAnimationFrame(tickStory);
    }
  }
  function tickStory(time) {
    storyFrame = 0;
    if (reduced.matches || !storyVisible()) { previousTime = 0; return; }
    if (previousTime) storyElapsed += Math.min(time - previousTime, 100);
    previousTime = time;
    const card = stories[storyIndex];
    showNow(card, storyElapsed >= 2500);
    card.querySelector('.progress-young').style.width = `${Math.min(100, storyElapsed / 25)}%`;
    card.querySelector('.progress-now').style.width = `${Math.max(0, Math.min(100, (storyElapsed - 2500) / 35))}%`;
    if (storyElapsed >= 6000) {
      if (manual || storyIndex === stories.length - 1) return;
      setStory(storyIndex + 1);
      animatingUntil = performance.now() + 650;
      const next = stories[storyIndex];
      rail.scrollTo({left: next.offsetLeft - (rail.clientWidth - next.clientWidth) / 2, behavior: 'smooth'});
    }
    storyFrame = requestAnimationFrame(tickStory);
  }
  if (rail) {
    const markManual = () => { manual = true; animatingUntil = 0; };
    rail.addEventListener('pointerdown', markManual, {passive: true});
    rail.addEventListener('wheel', markManual, {passive: true});
    rail.addEventListener('scroll', () => {
      if (performance.now() < animatingUntil) return;
      const center = rail.getBoundingClientRect().left + rail.clientWidth / 2;
      let closest = storyIndex;
      let distance = Infinity;
      stories.forEach((card, index) => {
        const rect = card.getBoundingClientRect();
        const delta = Math.abs(rect.left + rect.width / 2 - center);
        if (delta < distance) { closest = index; distance = delta; }
      });
      if (closest !== storyIndex) { manual = true; setStory(closest); }
      wakeStory();
    }, {passive: true});
    stories.forEach((card, index) => card.addEventListener('click', () => {
      manual = true;
      if (storyIndex !== index) setStory(index);
      cancelAnimationFrame(storyFrame);
      storyFrame = 0;
      storyElapsed = 6000;
      showNow(card, !card.classList.contains('show-now'));
    }));
    addEventListener('scroll', wakeStory, {passive: true});
    addEventListener('resize', wakeStory);
    document.addEventListener('visibilitychange', wakeStory);
    reduced.addEventListener('change', wakeStory);
  }

  // Desktop previews play for three seconds, then rewind to the source cue.
  // Small touch layouts play only the card visible within the horizontal rail.
  const videoStates = [...home.querySelectorAll('.video-card video')].map(video => {
    const card = video.closest('.video-card');
    const start = Number(video.dataset.startTime || 0);
    const state = {video, card, timer: 0, token: 0, playing: false};
    const rewind = () => { if (video.readyState >= 1) video.currentTime = start; };
    state.stop = () => {
      state.playing = false;
      state.token += 1;
      clearTimeout(state.timer);
      video.pause();
      rewind();
    };
    state.play = (limited = true) => {
      if (reduced.matches || document.hidden || state.playing) return;
      state.playing = true;
      const token = ++state.token;
      rewind();
      video.play().then(() => {
        if (token !== state.token) return;
        if (limited) state.timer = setTimeout(state.stop, 3000);
      }).catch(() => { if (token === state.token) state.playing = false; });
    };
    video.addEventListener('loadedmetadata', rewind, {once: true});
    if (video.readyState >= 1) rewind();
    card.addEventListener('mouseenter', () => { if (!touch.matches) state.play(); });
    card.addEventListener('mouseleave', state.stop);
    card.addEventListener('focus', () => state.play());
    card.addEventListener('blur', state.stop);
    return state;
  });
  function updateVideos() {
    videoStates.forEach(state => {
      const rect = state.card.getBoundingClientRect();
      const onScreen = !document.hidden && rect.bottom > 64 && rect.top < innerHeight;
      const mobileVisible = onScreen && Math.max(0, Math.min(rect.right, innerWidth) - Math.max(0, rect.left)) / rect.width >= .6;
      if (!onScreen || reduced.matches || (innerWidth <= 640 && !mobileVisible)) state.stop();
      else if (innerWidth <= 640 && mobileVisible) state.play(false);
    });
  }
  home.querySelector('.video-grid')?.addEventListener('scroll', updateVideos, {passive: true});
  addEventListener('scroll', updateVideos, {passive: true});
  addEventListener('resize', updateVideos);
  document.addEventListener('visibilitychange', updateVideos);
  reduced.addEventListener('change', updateVideos);

  home.querySelectorAll('.quote-trigger').forEach(trigger => {
    trigger.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); trigger.click(); }
    });
    trigger.addEventListener('click', () => {
      const reference = trigger.closest('.quote-reference');
      const open = !reference.classList.contains('open');
      closeQuotes();
      reference.classList.toggle('open', open);
      trigger.setAttribute('aria-expanded', String(open));
    });
  });
  function closeQuotes() {
    home.querySelectorAll('.quote-reference.open').forEach(reference => {
      reference.classList.remove('open');
      reference.querySelector('.quote-trigger').setAttribute('aria-expanded', 'false');
    });
  }
  document.addEventListener('pointerdown', event => { if (!event.target.closest('.quote-reference')) closeQuotes(); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closeQuotes(); });
  home.querySelectorAll('.partner-card').forEach(card => card.addEventListener('click', event => {
    if (touch.matches) { event.preventDefault(); card.classList.toggle('flipped'); }
  }));

  home.classList.add('motion-ready');
  updateBand();
  wakeStory();
  updateVideos();
})();
