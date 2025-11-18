/*----------------------------------------------
Index Of Script
------------------------------------------------

:: Before After Image
:: Header fixed
:: progress-bar
:: Vertical Slider
:: Setup-wizard

------------------------------------------------
Index Of Script
----------------------------------------------*/

(function (jQuery) {
  "use strict";

  // Before After Image
  jQuery(function () {
    function adjustSlider() {
      jQuery("#beforeimg-slider").on("input change", function (e) {
        const sliderPos = jQuery(this).val();
        jQuery(".foreground-img").css("width", `${sliderPos}%`);
        jQuery(".slider-button").css("left", `calc(${sliderPos}% - 18px)`);
      });
    }

    adjustSlider();
  });
  /*===================
    Header fixed
    ===========================*/
  jQuery(window).scroll(function () {
    var sticky = jQuery('header .iq-navbar'),
      scroll = jQuery(window).scrollTop();

    if (scroll >= 100) sticky.addClass('fixed');
    else sticky.removeClass('fixed');
  });

  /*===================
    progress-bar
    ===========================*/
  jQuery(function () {
    var circularProgress = jQuery(".iq-circle-progressbar");

    function checkVisibility() {
      var windowTop = jQuery(window).scrollTop();
      var windowBottom = windowTop + jQuery(window).height();

      circularProgress.each(function () {
        var elementTop = jQuery(this).offset().top;

        if (elementTop <= windowBottom && elementTop >= windowTop) {
          jQuery(this).addClass("active");
        }
      });
    }

    jQuery(document).scroll(function () {
      checkVisibility();
    });

    jQuery(window).resize(function () {
      checkVisibility();
    });

    checkVisibility(); // Check visibility on page load
  });

  /*---------------------------------------------------------------------
    Vertical Slider
    -----------------------------------------------------------------------*/

  if (document.querySelectorAll(".slider__thumbs .swiper-container").length) {
    const sliderThumbsOptions = {
      direction: "vertical",
      slidesPerView: 3,
      spaceBetween: 24,
      slideToClickedSlide: true,
      loop: true,
      loopedSlides: 5,
      navigation: {
        nextEl: ".slider__next",
        prevEl: ".slider__prev",
      },
      breakpoints: {
        0: {
          direction: "horizontal",
          slidesPerView: 3,
        },
        768: {
          direction: "vertical",
        },
      },
    };
    const sliderImagesOptions = {
      direction: "vertical",
      slidesPerView: 1,
      spaceBetween: 32,
      loop: true,
      loopedSlides: 5,
      mousewheel: true,
      navigation: {
        nextEl: ".slider__next",
        prevEl: ".slider__prev",
      },
      grabCursor: true,
      breakpoints: {
        0: {
          direction: "horizontal",
        },
        768: {
          direction: "vertical",
        },
      },
    };
    let sliderThumbs = new Swiper(
      ".slider__thumbs .swiper-container",
      sliderThumbsOptions
    );
    let sliderImages = new Swiper(
      ".slider__images .swiper-container",
      sliderImagesOptions
    );
    sliderThumbs.controller.control = sliderImages;
    sliderImages.controller.control = sliderThumbs;
    document.addEventListener("theme_scheme_direction", (e) => {
      sliderImages.destroy(true, true);
      setTimeout(() => {
        sliderThumbs = new Swiper(
          ".slider__thumbs .swiper-container",
          sliderThumbsOptions
        );
        sliderImages = new Swiper(
          ".slider__images .swiper-container",
          sliderImagesOptions
        );
        sliderThumbs.controller.control = sliderImages;
        sliderImages.controller.control = sliderThumbs;
      }, 500);
    });
  }

  const valuesNode = [
    document.getElementById("lower-value"), // 0
    document.getElementById("upper-value"), // 1
  ];
  window.addEventListener("load", function () {
    if (window["product-price-range"]) {
      window["product-price-range"].on(
        "update",
        function (values, handle, unencoded, isTap, positions) {
          valuesNode[handle].innerHTML =
            "$" + Number(values[handle]).toFixed(0);
        }
      );
    }
    const pageType = IQUtils.getQueryString("type");
    switch (pageType) {
      case "product-grid":
        $(".breadcrumb-title small").text("Product Grid View");
        $(".sidebar .product-grid")
          .addClass("active")
          .parent()
          .addClass("active");
        $(".sidebar .product-grid")
          .closest(".collapse")
          .addClass("show")
          .prev()
          .attr("aria-expanded", true)
          .parent()
          .addClass("active");
        $("#grid-view-tab").tab("show");
        break;
      case "product-list":
        $(".breadcrumb-title small").text("Product List View");
        $(".sidebar .product-list")
          .addClass("active")
          .parent()
          .addClass("active");
        $(".sidebar .product-list")
          .closest(".collapse")
          .addClass("show")
          .prev()
          .attr("aria-expanded", true)
          .parent()
          .addClass("active");
        $("#list-view-tab").tab("show");
        break;
      default:
        break;
    }
  });

  /*---------------------------------------------------------------------
    Setup-wizard
  -----------------------------------------------------------------------*/
  jQuery(document).ready(function () {
    // hidden things
    jQuery(".appointment-tab-content").hide();
    jQuery("#successMessage").hide();
    // next button
    jQuery(".next").on({
      click: function () {
        jQuery("#appointment-tab-list").find(".active").next().addClass("active");
        jQuery("#appointment-tab-list").find(".active").prev().addClass("done");
        jQuery(this).parents(".appointment-content-active").fadeOut("slow", function () {
          jQuery(this).next(".appointment-content-active").fadeIn("slow");
        });
      }
    });

    // back button
    jQuery(".back").on({
      click: function () {
        jQuery("#appointment-tab-list").find(".active").last().removeClass("active");
        jQuery("#appointment-tab-list").find(".done").last().removeClass("done");
        jQuery(this).parents(".appointment-content-active").fadeOut("slow", function () {
          jQuery(this).prev(".appointment-content-active").fadeIn("slow");
        });
      }
    });

    // Confirm button
    jQuery(".confirm-button").on({
      click: function () {
        jQuery("#appointment-tab-list").find(".active").addClass("done");
        jQuery(this).parents(".appointment-content-active").fadeOut("slow", function () {
          jQuery(this).next(".appointment-content-active").fadeIn("slow");
        });
      }
    });
  });
})(jQuery);