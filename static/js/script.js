$(document).ready(function() {
    function startProcessing() {
        let formData = new FormData($('#videoForm')[0]);

        $.ajax({
            url: '/compress_video_logic',
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                updateLogArea(response.message);
                pollCompletion();
            },
            error: function(error) {
                let errorMessage = 'Unknown error occurred';
                if (error.responseJSON && error.responseJSON.error) {
                    errorMessage = error.responseJSON.error;
                }
                updateLogArea('错误: ' + errorMessage);
            }
        });
    }

    function get_video_info() {
        let formData = new FormData($('#videoForm')[0]);

        $.ajax({
            url: '/get_video_info',
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                updateLogArea(response.message);
            },
            error: function(error) {
                let errorMessage = 'Unknown error occurred';
                if (error.responseJSON && error.responseJSON.error) {
                    errorMessage = error.responseJSON.error;
                }
                updateLogArea('错误: ' + errorMessage);
            }
        });
    }

    function compress_video_logic() {
        let formData = new FormData($('#videoForm')[0]);

        $.ajax({
            url: '/compress_video_logic',
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                updateLogArea(response.message);
                pollCompletion();
            },
            error: function(error) {
                let errorMessage = 'Unknown error occurred';
                if (error.responseJSON && error.responseJSON.error) {
                    errorMessage = error.responseJSON.error;
                }
                updateLogArea('错误: ' + errorMessage);
            }
        });
    }

    function stopProcessing() {
        $.ajax({
            url: '/stop_processing',
            method: 'POST',
            success: function(response) {
                updateLogArea(response.message);
            },
            error: function(error) {
                let errorMessage = 'Unknown error occurred';
                if (error.responseJSON && error.responseJSON.error) {
                    errorMessage = error.responseJSON.error;
                }
                updateLogArea('错误: ' + errorMessage);
            }
        });
    }

    function updateLogArea(message) {
        let logArea = $('#logArea');
        logArea.val(logArea.val() + message + '\n');
        logArea.scrollTop(logArea[0].scrollHeight);
    }

    function clearLog() {
        $('#logArea').val('');
        $('#downloadArea').empty();
        $('#videoFile').val('');  // 清除文件输入框的值
    }

    function updateDownloadLinks(file) {
        let downloadArea = $('#downloadArea');
        downloadArea.empty();
        let link = $('<a></a>').attr('href', '/download/' + file).attr('download', file).text(file);
        downloadArea.append(link).append('<br>');
    }

    function pollCompletion() {
        let interval = setInterval(() => {
            $.ajax({
                url: '/completion',
                method: 'GET',
                success: function(response) {
                    if (response.completed_files.length > 0) {
                        clearInterval(interval);
                        response.completed_files.forEach(file => {
                            updateDownloadLinks(file);
                        });
                    }
                }
            });
        }, 1000); // 每秒检查一次
    }

    // 定时获取日志
    setInterval(function() {
        $.ajax({
            url: '/logs',
            method: 'GET',
            success: function(response) {
                let logText = response.logs.join('\n');
                if (logText.trim() !== '') {
                    updateLogArea(logText);
                }
            }
        });
    }, 5000); // 将刷新频率降低到每5秒一次

    // 绑定函数到全局对象，使其在HTML中可访问
    window.startProcessing = startProcessing;
    window.get_video_info = get_video_info;
    window.compress_video_logic = compress_video_logic;
    window.stopProcessing = stopProcessing;
    window.clearLog = clearLog;
});
