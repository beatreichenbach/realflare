var debounce = function (fn) {
    var frame;
    return function () {
        var params = [];
        for (var _i = 0; _i < arguments.length; _i++) {
            params[_i] = arguments[_i];
        }
        if (frame) {
            cancelAnimationFrame(frame);
        }
        frame = requestAnimationFrame(function () {
            fn.apply(void 0, params);
        });
    };
};
var header = document.querySelector(".md-header");
var hero = document.querySelector(".mdx-parallax__group");
var updateHtml = function () {
    var aboveContent = parallax.scrollTop < hero.offsetTop + hero.offsetHeight;
    if (aboveContent) {
        header.classList.remove("md-header--shadow");
    }
    else {
        header.classList.add("md-header--shadow");
    }
};
var parallax = document.querySelector(".mdx-parallax");
parallax.addEventListener("scroll", debounce(updateHtml), { passive: true });
updateHtml();
var video_parent = document.querySelector(".mdx-parallax__group:first-child");
var video = document.querySelector(".mdx-hero__video video");
var scroll_video = function () {
    if (video.duration) {
        var scrolled = parallax.scrollTop / video_parent.scrollHeight;
        var time = Math.min(Math.max(scrolled, 0), 1);
        video.currentTime = video.duration * time;
        requestAnimationFrame(function () { });
    }
};
parallax.addEventListener("scroll", scroll_video);
//# sourceMappingURL=custom.js.map