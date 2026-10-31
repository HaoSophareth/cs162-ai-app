// Month view: go to the previous or next month by swiping sideways
// (trackpad or touch screen) or with the left/right arrow keys. It just follows
// the ‹ › links, so the pages work the same without JavaScript.

// Tell the next page which way to slide (see "slide" in style.css).
// This must run before the page is first drawn, so the script sits in <head>.
window.addEventListener("pagereveal", (event) => {
  const direction = sessionStorage.getItem("slide");
  sessionStorage.removeItem("slide");
  if (event.viewTransition && direction) {
    event.viewTransition.types.add(direction);
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const links = {
    prev: document.querySelector('[data-nav="prev"]'),
    next: document.querySelector('[data-nav="next"]'),
  };
  let leaving = false;

  function go(direction) {
    if (leaving) return; // one swipe = one page, even if events keep coming
    leaving = true;
    sessionStorage.setItem("slide", direction);
    location.href = links[direction].href;
  }

  for (const direction of ["prev", "next"]) {
    links[direction].addEventListener("click", () => sessionStorage.setItem("slide", direction));
  }

  // Trackpad: add up sideways scrolling until it's clearly a swipe.
  let sideways = 0;
  let resetTimer;
  window.addEventListener("wheel", (event) => {
    if (Math.abs(event.deltaX) <= Math.abs(event.deltaY)) return; // normal up/down scroll
    event.preventDefault();
    sideways += event.deltaX;
    clearTimeout(resetTimer);
    resetTimer = setTimeout(() => (sideways = 0), 300);
    if (sideways > 100) go("next");
    if (sideways < -100) go("prev");
  }, { passive: false });

  // Touch screen: compare where the finger started and ended.
  let startX = 0;
  let startY = 0;
  window.addEventListener("touchstart", (event) => {
    startX = event.touches[0].clientX;
    startY = event.touches[0].clientY;
  });
  window.addEventListener("touchend", (event) => {
    const dx = event.changedTouches[0].clientX - startX;
    const dy = event.changedTouches[0].clientY - startY;
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy)) {
      go(dx < 0 ? "next" : "prev");
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.target.closest("input, textarea, select")) return;
    if (event.key === "ArrowRight") go("next");
    if (event.key === "ArrowLeft") go("prev");
  });
});
