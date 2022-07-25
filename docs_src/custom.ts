const debounce = (fn: Function) => {
  let frame: number;
  return (...params: any[]) => {
    if (frame) {
      cancelAnimationFrame(frame);
    }

    frame = requestAnimationFrame(() => {
      fn(...params);
    });
  };
};

const header: HTMLElement = document.querySelector(".md-header");
const hero: HTMLElement = document.querySelector(".mdx-parallax__group");
const updateHtml = () => {
  const aboveContent = parallax.scrollTop < hero.offsetTop + hero.offsetHeight;
  if (aboveContent) {
    header.classList.remove("md-header--shadow");
  } else {
    header.classList.add("md-header--shadow");
  }
};
// Listen for new scroll events, here we debounce our `updateHtml` function
const parallax: HTMLElement = document.querySelector(".mdx-parallax");
parallax.addEventListener("scroll", debounce(updateHtml), { passive: true });

// Update scroll position for first time
updateHtml();

const video_parent: HTMLElement = document.querySelector(
  ".mdx-parallax__group:first-child"
);
const video: HTMLVideoElement = document.querySelector(
  ".mdx-hero__video video"
);

const scroll_video = () => {
  if (video.duration) {
    const scrolled = parallax.scrollTop / video_parent.scrollHeight;
    const time = Math.min(Math.max(scrolled, 0), 1);
    video.currentTime = video.duration * time;
    requestAnimationFrame(() => {});
  }
};

parallax.addEventListener("scroll", debounce(scroll_video));

const show_hidden = () => {
  transition_elements.forEach((element) => {
    const rect = element.getBoundingClientRect();
    const visible =
      rect.top <= (window.innerHeight || document.documentElement.clientHeight);
    if (visible) {
      element.removeAttribute("hidden");
      transition_elements.splice(transition_elements.indexOf(element), 1);
    }
  });
  if (transition_elements.length == 0) {
    parallax.removeEventListener("scroll", show_hidden_debounce);
  }
};
const transition_elements = [
  ...document.querySelectorAll(".mdx-parallax [hidden]"),
];
const show_hidden_debounce = debounce(show_hidden);
parallax.addEventListener("scroll", show_hidden_debounce, { passive: true });
