(function (jQuery) {
    "use strict";

    callGeneralSwiper();

})(jQuery);

function callGeneralSwiper() {
    jQuery(document).find('.swiper.swiper-general').each(function () {
        let slider = jQuery(this);

        var sliderAutoplay = slider.data('autoplay');

        var breakpoint = {
            // when window width is >= 0px
            0: {
                slidesPerView: slider.data('mobile-sm'),
                spaceBetween: 30,
            },
            576: {
                slidesPerView: slider.data('mobile'),
                spaceBetween: 30,
            },
            // when window width is >= 768px
            768: {
                slidesPerView: slider.data('tab'),
                spaceBetween: 30,
            },
            // when window width is >= 1025px
            1025: {
                slidesPerView: slider.data('laptop'),
                spaceBetween: 30,
            },
            // when window width is >= 1500px
            1500: {
                slidesPerView: slider.data('slide'),
                spaceBetween: 30,
            },
        }

        if (slider.data('navigation')) {
            var navigationVal = {
                nextEl: slider.find('.swiper-button-next')[0],
                prevEl: slider.find('.swiper-button-prev')[0],
            };
        } else {
            var navigationVal = false;
        }

        if (slider.data('pagination')) {
            var paginationVal = {
                el: slider.find(".swiper-pagination")[0],
                dynamicBullets: true,
                clickable: true,
            };
        } else {
            var paginationVal = false;
        }
        var sw_config = {
            loop: slider.data('loop'),
            speed: 1000,
            spaceBetween: 30,
            slidesPerView: slider.data('slide'),
            centeredSlides: slider.data('center'),
            mousewheel: slider.data('mousewheel'),
            autoplay: sliderAutoplay,
            effect: slider.data('effect'),
            navigation: navigationVal,
            pagination: paginationVal,
            breakpoints: breakpoint,
        };
        var swiper = new Swiper(slider[0], sw_config);
    });
}