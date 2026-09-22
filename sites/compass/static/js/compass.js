'use strict';
const dialogOpeners = new WeakMap();
for (const button of document.querySelectorAll('[data-open-dialog]')) {
  button.addEventListener('click', () => {
    const dialog = document.getElementById(button.dataset.openDialog);
    if (!dialog) return;
    dialogOpeners.set(dialog, button);
    dialog.showModal();
    (dialog.querySelector('[data-close-dialog]') || dialog.querySelector('input,select,button,a[href]'))?.focus();
  });
}
for (const button of document.querySelectorAll('[data-close-dialog]')) {
  button.addEventListener('click', () => button.closest('dialog')?.close());
}
for (const dialog of document.querySelectorAll('dialog')) {
  dialog.addEventListener('click', event => { if (event.target === dialog) { const box = dialog.getBoundingClientRect(); if(event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close(); } });
  dialog.addEventListener('close', () => dialogOpeners.get(dialog)?.focus());
}
const gallery=document.getElementById('photo-viewer');
if(gallery) {
  const photos=[...document.querySelectorAll('[data-gallery-src]')];
  const image=gallery.querySelector('img'), counter=gallery.querySelector('[data-photo-counter]');
  let index=0;
  function show(next) { index=(next+photos.length)%photos.length; image.src=photos[index].dataset.gallerySrc; image.alt=photos[index].querySelector('img').alt; counter.textContent=(index+1)+' / '+photos.length; }
  for(const [number,photo] of photos.entries()) photo.addEventListener('click',()=>{show(number);gallery.showModal();});
  document.querySelector('[data-view-photos]')?.addEventListener('click',()=>{show(0);gallery.showModal();});
  gallery.querySelector('[data-previous-photo]').addEventListener('click',()=>show(index-1));
  gallery.querySelector('[data-next-photo]').addEventListener('click',()=>show(index+1));
  gallery.addEventListener('keydown',event=>{ if(event.key==='ArrowLeft'){event.preventDefault();show(index-1);} if(event.key==='ArrowRight'){event.preventDefault();show(index+1);} });
}

document.querySelector('[data-copy-property-link]')?.addEventListener('click',async()=>{
  const input=document.getElementById('property-share-link');
  const status=document.querySelector('[data-copy-status]');
  try {await navigator.clipboard.writeText(input.value);status.textContent='Link copied.';}
  catch {input.focus();input.select();status.textContent='Select and copy the link above.';}
});

// Source navigation dropdowns: keep one open, and close on Escape or outside click.
const navigationMenus = [...document.querySelectorAll('.nav-menu')];
for (const menu of navigationMenus) {
  menu.addEventListener('toggle', () => {
    if (menu.open) for (const other of navigationMenus) if (other !== menu) other.open = false;
  });
}
document.addEventListener('click', event => {
  for (const menu of navigationMenus) if (!menu.contains(event.target)) menu.open = false;
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') for (const menu of navigationMenus) {
    if (menu.open && menu.contains(document.activeElement)) menu.querySelector('summary').focus();
    menu.open = false;
  }
});
for (const button of document.querySelectorAll('.market-toggle,.footer-toggle')) {
  button.addEventListener('click', () => {
    const expanded = button.getAttribute('aria-expanded') !== 'true';
    button.setAttribute('aria-expanded', String(expanded));
    const icon = button.querySelector('span');
    if (icon) icon.textContent = expanded ? '−' : '＋';
  });
}
for (const frame of document.querySelectorAll('[data-home-gallery]')) {
  const photos = JSON.parse(frame.dataset.homeGallery);
  if (photos.length < 2) continue;
  const image = frame.querySelector('img');
  const counter = frame.querySelector('.home-photo-count');
  let index = 0;
  function showPhoto(next) {
    index = (next + photos.length) % photos.length;
    image.src = photos[index];
    counter.textContent = `${index + 1}/${photos.length}`;
  }
  frame.querySelector('[data-home-previous]')?.addEventListener('click', event => { event.preventDefault(); event.stopPropagation(); showPhoto(index - 1); });
  frame.querySelector('[data-home-next]')?.addEventListener('click', event => { event.preventDefault(); event.stopPropagation(); showPhoto(index + 1); });
}
