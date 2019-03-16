/* globals $:false, RobustWebSocket:false */
/* eslint no-plusplus: off */

$(function() {
    const newGrid = (_selector) => {
        const selector = $(_selector);

        for (let y = 0; y < 16; y++) {
            for (let x = 0; x < 16; x++) {
                const div = $('<div/>', { id: `${x}_${y}` }).addClass('led');
                $(selector).append(div);
            }
        }

        return {
            draw: (pixmap) => {
                for (let y = 0; y < 16; y++) {
                    for (let x = 0; x < 16; x++) {
                        const [r, g, b] = pixmap[y * 16 + x];
                        $(`div#${x}_${y}`).css({ 'background-color': `rgb(${r},${g},${b})` });
                    }
                }
            }
        };
    };

    // Prevent context menus....

    window.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        e.stopPropagation();
    });

    // Create our grid

    const grid = newGrid('.divoom-grid');

    // eslint-disable-next-line
    const url = 'ws' + (location.protocol === 'https:' ? 's' : '') + '://' + $(location).attr('host') + '/evo/ws';
    const ws = new RobustWebSocket(url);

    ws.addEventListener('open', function(/*event*/) {
        ws.send('Browser connected!');
    });

    ws.addEventListener('close', function(/*event*/) {
        ws.send('Browser bye!');
    });

    ws.addEventListener('message', function(event) {
        const data = JSON.parse(event.data);
        if (data.type === 'pixmap') {
            grid.draw(data.pixmap);
        }
    });

    $('.divoom-grid').on('swipeleft', (event) => {
        event.stopPropagation();
        $.ajax({
            type: 'POST',
            dataType: 'json',
            contentType: 'application/json',
            url: '/evo/mode',
            data: JSON.stringify({ mode: 'next' })
        });
    });

    $('.divoom-grid').on('dragstart', false);

    $('.divoom-grid').on('swiperight', (event) => {
        event.stopPropagation();
        $.ajax({
            type: 'POST',
            dataType: 'json',
            contentType: 'application/json',
            url: '/evo/mode',
            data: JSON.stringify({ mode: 'prev' })
        });
    });

    // Will trigger when a file is selected
    $('#file_button').on('change', () => {
        $('#upload_form').submit();
    });

    // Upload file...
    $('.divoom-grid').on('taphold doubletap', () => {
        $('#file_button').trigger('click');
    });

    $('.pure-button').on('click', (event) => {
        const mode = $(event.target).data('mode');

        $.ajax({
            type: 'POST',
            dataType: 'json',
            contentType: 'application/json',
            url: '/evo/mode',
            data: JSON.stringify({ mode: mode })
        });
    });
});
