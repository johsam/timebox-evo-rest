/* globals RobustWebSocket:false */
/* eslint no-plusplus: off */

// eslint-disable-next-line prefer-arrow-callback
$(function() {
    const newGrid = (_selector) => {
        const selector = $(_selector);
        const _cache = [];

        for (let y = 0; y < 16; y++) {
            for (let x = 0; x < 16; x++) {
                const div = $('<div/>', { id: `${x}_${y}` }).addClass('led');
                const inner = $('<div/>', { class: 'led-inner' });
                div.append(inner);

                $(selector).append(div);
                _cache.push($(inner));
            }
        }

        return {
            draw: (pixmap) => {
                for (let y = 0; y < 16; y++) {
                    for (let x = 0; x < 16; x++) {
                        const [r, g, b] = pixmap[y * 16 + x];
                        //_cache[y * 16 + x].css({ 'background-color': `rgb(${r},${g},${b})` });
                        _cache[y * 16 + x].css({
                            background: `-webkit-radial-gradient(rgba(${r},${g},${b},1) 0%, rgba(255,255,255,0) 100%)`
                        });
                    }
                }
            },
            delta: (delta) => {
                //console.log('Delta pixels = ',delta.length)
                for (let i = 0; i < delta.length; i++) {
                    const [x, y, [r, g, b]] = delta[i];
                    //_cache[y * 16 + x].css({ 'background-color': `rgb(${r},${g},${b})` });

                    _cache[y * 16 + x].css({
                        background: `-webkit-radial-gradient(rgba(${r},${g},${b},1) 0%, rgba(255,255,255,0) 100%)`
                    });

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

    ws.addEventListener('open', (/*event*/) => {
        ws.send('Browser connected!');
    });

    // eslint-disable-next-line prefer-arrow-callback
    ws.addEventListener('close', function(/*event*/) {
        ws.send('Browser bye!');
    });

    ws.addEventListener('message', (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'pixmap') {
            //console.log('Got pixmap bytes =', event.data.length);
            grid.draw(data.pixmap);
        }
        if (data.type === 'delta') {
            //console.log('Got delta bytes =', event.data.length);
            grid.delta(data.delta);
        }
    });

    $('.divoom-grid').on('dragstart', false);

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
    $('.divoom-grid').on('taphold doubletap', (event) => {
        event.stopPropagation();
        $('#file_button').trigger('click');
    });

    $('.pure-button').on('click', (event) => {
        event.stopPropagation();
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
