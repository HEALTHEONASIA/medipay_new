(function($) {
    'use strict';
    $(document).ready(function() {
        var drawSparklinePieByStatus = function() {
            // $("#sparkline-pie-by-status").sparkline([2, 1, 1, 1], {
            $("#sparkline-pie-by-status").sparkline(byStatusCount, {
                type: 'pie',
                width: '250',
                height: '250',
                tooltipFormat: '{{offset:offset}} ({{count}} {{percent.1}}%)',
                tooltipValueLookups: {
                    'offset': {
                        0: 'Approved: ' + byStatusCount[0],
                        1: 'Rejected: ' + byStatusCount[1],
                        2: 'In Review: ' + byStatusCount[2],
                        3: 'Pending: ' + byStatusCount[3]
                    }
                },
                /* Color Slices Take Up RGBA Values */
                sliceColors: [$.Pages.getColor('master-dark'), $.Pages.getColor('complete-dark'), $.Pages.getColor('complete-light'), $.Pages.getColor('master-light')]
            });
        }
        var drawSparklinePieByCountry = function() {
            // $("#sparkline-pie-by-country").sparkline([40, 30, 20, 10], {
            $("#sparkline-pie-by-country").sparkline(byCountryCount, {
                type: 'pie',
                width: '250',
                height: '250',
                tooltipFormat: '{{offset:offset}} ({{percent.1}}%)',
                tooltipValueLookups: {
                    'offset': byCountryLabel
                },
                /* Color Slices Take Up RGBA Values */
                sliceColors: [$.Pages.getColor('master-dark'), $.Pages.getColor('complete-dark'), $.Pages.getColor('complete-light'), $.Pages.getColor('master-light')]
            });
        }
        var drawSparklinePieByProvider = function() {
            // $("#sparkline-pie-by-provider").sparkline([4, 3, 2, 1], {
            $("#sparkline-pie-by-provider").sparkline(byProviderCount, {
                type: 'pie',
                width: '250',
                height: '250',
                tooltipFormat: '{{offset:offset}} ({{percent.1}}%)',
                tooltipValueLookups: {
                    'offset': byProviderLabel
                },
                /* Color Slices Take Up RGBA Values */
                sliceColors: [$.Pages.getColor('master-dark'), $.Pages.getColor('complete-dark'), $.Pages.getColor('complete-light'), $.Pages.getColor('master-light')]
            });
        }
        var drawSparklinePieByPayer = function() {
            // $("#sparkline-pie-by-payer").sparkline([40, 30, 20, 10], {
            $("#sparkline-pie-by-payer").sparkline(byPayerCount, {
                type: 'pie',
                width: '250',
                height: '250',
                tooltipFormat: '{{offset:offset}} ({{percent.1}}%)',
                tooltipValueLookups: {
                    'offset': byPayerLabel
                },
                /* Color Slices Take Up RGBA Values */
                sliceColors: [$.Pages.getColor('master-dark'), $.Pages.getColor('complete-dark'), $.Pages.getColor('complete-light'), $.Pages.getColor('master-light')]
            });
        }
        drawSparklinePieByStatus();
        drawSparklinePieByCountry();
        drawSparklinePieByProvider();
        drawSparklinePieByPayer();
    });
})(window.jQuery);
