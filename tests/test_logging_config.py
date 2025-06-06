from loguru import logger

from src.k3s_deploy_cli.logging_config import VERBOSE_LOG_LEVEL, configure_logging


def test_default_configuration(capture_logs):
    configure_logging(verbose=False, debug=False)
    logger.info("Test INFO message")
    assert any("Test INFO message" in log for log in capture_logs.logs)


def test_verbose_configuration(capture_logs):
    configure_logging(verbose=True, debug=False)
    logger.log(VERBOSE_LOG_LEVEL, "Test VERBOSE message")
    assert any("Test VERBOSE message" in log for log in capture_logs.logs)


def test_debug_configuration(capture_logs):
    configure_logging(verbose=False, debug=True)
    logger.debug("Test DEBUG message")
    assert any("Test DEBUG message" in log for log in capture_logs.logs)


def test_verbose_and_debug_configuration(capture_logs):
    configure_logging(verbose=True, debug=True)
    logger.debug("Test DEBUG message")
    assert any("Test DEBUG message" in log for log in capture_logs.logs)


def test_handler_removal(capture_logs):
    configure_logging(verbose=False, debug=False)
    logger.info("First INFO message")
    # Clear logs to test handler replacement
    capture_logs.logs.clear()
    configure_logging(verbose=True, debug=False)
    logger.log(VERBOSE_LOG_LEVEL, "Second VERBOSE message")
    # After handler reconfiguration, the new message should be captured
    assert any("Second VERBOSE message" in log for log in capture_logs.logs)
    # The capture should only contain the new message (no duplication from old handlers)
    verbose_messages = [log for log in capture_logs.logs if "Second VERBOSE message" in log]
    assert len(verbose_messages) == 1


def test_exception_logging(capture_logs):
    configure_logging(debug=True)
    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("Test exception")
    assert any("Test exception" in log for log in capture_logs.logs)
    assert any("ZeroDivisionError" in log for log in capture_logs.logs)


def test_handler_without_sink_attribute(capture_logs):
    """Test edge case where a handler doesn't have _sink attribute (line 29)"""
    from unittest.mock import Mock
    
    # Create a mock handler without _sink attribute
    mock_handler = Mock()
    # Ensure it doesn't have _sink attribute
    if hasattr(mock_handler, '_sink'):
        delattr(mock_handler, '_sink')
    
    # Add the mock handler to logger's handlers
    test_handler_id = 999
    logger._core.handlers[test_handler_id] = mock_handler
    
    try:
        # This should not raise an error and should skip the handler without _sink
        configure_logging(verbose=False, debug=False)
        
        # Verify the mock handler is still there (wasn't removed)
        assert test_handler_id in logger._core.handlers
        
        # Test that normal logging still works
        logger.info("Test message after handler without sink")
        assert any("Test message after handler without sink" in log for log in capture_logs.logs)
        
    finally:
        # Clean up: remove our mock handler
        if test_handler_id in logger._core.handlers:
            del logger._core.handlers[test_handler_id]


def test_handler_with_different_sink(capture_logs):
    """Test edge case where a handler has _sink but it's not sys.stderr (line 31)"""
    from io import StringIO
    from unittest.mock import Mock
    
    # Create a mock handler with a different sink (not sys.stderr)
    mock_handler = Mock()
    mock_handler._sink = StringIO()  # Different sink, not sys.stderr
    
    # Add the mock handler to logger's handlers
    test_handler_id = 998
    logger._core.handlers[test_handler_id] = mock_handler
    
    try:
        # This should not remove the handler since its sink is not sys.stderr
        configure_logging(verbose=False, debug=False)
        
        # Verify the mock handler is still there (wasn't removed because sink != sys.stderr)
        assert test_handler_id in logger._core.handlers
        
        # Test that normal logging still works
        logger.info("Test message after handler with different sink")
        assert any("Test message after handler with different sink" in log for log in capture_logs.logs)
        
    finally:
        # Clean up: remove our mock handler
        if test_handler_id in logger._core.handlers:
            del logger._core.handlers[test_handler_id]


def test_stderr_handler_removal(capture_logs):
    """Test that handlers with sys.stderr sink are actually removed (lines 32, 35)"""
    import sys
    from unittest.mock import Mock
    
    # Create a mock handler with sys.stderr as sink
    mock_stderr_handler = Mock()
    mock_stderr_handler._sink = sys.stderr
    
    # Add the mock handler to logger's handlers
    test_handler_id = 997
    logger._core.handlers[test_handler_id] = mock_stderr_handler
    
    try:
        # Verify the handler is there before configuration
        assert test_handler_id in logger._core.handlers
        
        # This should remove the handler since its sink is sys.stderr (lines 32, 35)
        configure_logging(verbose=False, debug=False)
        
        # Verify the mock stderr handler was removed
        assert test_handler_id not in logger._core.handlers
        
        # Test that normal logging still works
        logger.info("Test message after stderr handler removal")
        assert any("Test message after stderr handler removal" in log for log in capture_logs.logs)
        
    finally:
        # Clean up: remove our mock handler if it's still there
        if test_handler_id in logger._core.handlers:
            del logger._core.handlers[test_handler_id]