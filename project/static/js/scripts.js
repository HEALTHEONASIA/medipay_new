(function($) {
    'use strict';
    $(document).ready(function() {
        $(".list-view-wrapper").scrollbar();
        $('.search-results').fadeOut();
        $('[data-pages="search"]').search({
            searchField: '#overlay-search',
            closeButton: '.overlay-close',
            suggestions: '#overlay-suggestions',
            brand: '.brand',
            onSearchSubmit: function(searchString) {
                console.log("Search for: " + searchString);
                var searchField = $('#overlay-search');
                var searchResults = $('.search-results');
                var searchResultsBlock = $('#search-results');
                var innerHtml;
                clearTimeout($.data(this, 'timer'));
                searchResults.fadeOut("fast");
                searchResultsBlock.html('');
                var wait = setTimeout(function() {
                    searchResults.find('.result-name').each(function() {
                        if (searchField.val().length != 0) {
                            $(this).html(searchField.val());
                            $.get('/search', {query: searchField.val()}, function(data) {
                                console.log(data);
                                if (data['results'].length != 0) {
                                    for (var key in data['results']) {
                                        innerHtml = '<a href="/request/';
                                        innerHtml += data['results'][key];
                                        innerHtml += '?query=' + searchField.val();
                                        innerHtml += '" target="_blank">GOP #';
                                        innerHtml += data['results'][key] + '</a>';
                                        searchResultsBlock.append('<p class="hint-text">' + innerHtml + '</p>');
                                    }
                                } else {
                                    searchResultsBlock.append('<p class="hint-text">No results found.</p>');
                                }
                            });
                            searchResults.fadeIn("fast");
                        }
                    });
                }, 500);
                $(this).data('timer', wait);
            },
            // onKeyEnter: function(searchString) {
            //     console.log("Live search for: " + searchString);
            //     var searchField = $('#overlay-search');
            //     var searchResults = $('.search-results');
            //     clearTimeout($.data(this, 'timer'));
            //     searchResults.fadeOut("fast");
            //     var wait = setTimeout(function() {
            //         searchResults.find('.result-name').each(function() {
            //             if (searchField.val().length != 0) {
            //                 $(this).html(searchField.val());
            //                 searchResults.fadeIn("fast");
            //             }
            //         });
            //     }, 500);
            //     $(this).data('timer', wait);
            // }
        })
    });
    $('.panel-collapse label').on('click', function(e) {
        e.stopPropagation();
    })
})(window.jQuery);