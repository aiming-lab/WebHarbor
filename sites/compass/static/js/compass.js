'use strict';
for (const button of document.querySelectorAll('[data-open-dialog]')) {
  button.addEventListener('click', () => document.getElementById(button.dataset.openDialog).showModal());
}
for (const button of document.querySelectorAll('[data-close-dialog]')) {
  button.addEventListener('click', () => button.closest('dialog').close());
}
for (const dialog of document.querySelectorAll('dialog')) {
  dialog.addEventListener('click', event => { if (event.target === dialog) { const box = dialog.getBoundingClientRect(); if(event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close(); } });
}
// Associate existing form labels with their controls for keyboard and screen readers.
for (const [index, field] of [...document.querySelectorAll('.field,.filter-group')].entries()) {
  const label=field.querySelector('label'), input=field.querySelector('input,select,textarea');
  if(label && input && !label.contains(input)) { input.id ||= 'field-'+index; label.htmlFor=input.id; }
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
