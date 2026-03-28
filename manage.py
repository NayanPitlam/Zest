from app import app

# Use the test_cli_runner to invoke the command. This sets up the necessary context.
cli_runner = app.test_cli_runner()
result = cli_runner.invoke(args=['init-db'])

if result.exit_code == 0:
    print(result.output)
else:
    print(f"Error: Command failed with exit code {result.exit_code}")
    print("Output:")
    print(result.output)
    if result.exception:
        print("Exception:")
        import traceback
        traceback.print_exception(type(result.exception), result.exception, result.exc_info[2])
