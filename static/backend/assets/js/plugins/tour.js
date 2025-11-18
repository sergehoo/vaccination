(function(window) {
  document.addEventListener('DOMContentLoaded', function (){
    const tour = new Shepherd.Tour({
      defaultStepOptions: {
        cancelIcon: {
          enabled: true
        },
        classes: 'class-1 class-2',
        scrollTo: { behavior: 'smooth', block: 'center' },
        when: {
          cancel: function () {
            IQUtils.saveSessionStorage('tour', 'true');
          }
        }
      },
    });

    // check media screen
    if (window.matchMedia('(min-width: 1198px)').matches) {
      setTimeout(() => {
        const liveCusomizer = IQUtils.getQueryString('live-customizer')
        if(liveCusomizer != 'open') {
          if(IQUtils.getSessionStorage('tour') !== 'true') {
            tour.start();
            $('.shepherd-modal-overlay-container').addClass('shepherd-modal-is-visible')
          }
        }
      }, 400)
    }
  })
})(window)
