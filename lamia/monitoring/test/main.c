/* Testing app for the `shadow' supervisor script.
 * */
# include <stdio.h>

void
print_usage(const char * appName, FILE * f) {
    fprintf( f, "Usage:\n\t$ %s <mode> <pause>\n", appName );
    fprintf( f, "Mimics the real application with its logging system and delays."
            " Available modes:\n"
            " * noreport -- do not print any progress message. However, various"
            " ASCII garbage will be printed to stdout/stderr.\n"
            " * events -- from time to time, prints \"Event <eventNo>/2000"
            " (some)\" message pretending simple practical case.\n"
            " * files -- from time to time, prints \"File\\n\\t<filename> read.\""
            " message mimicing practical case of multi-line message.\n");

}
int
main(int argc, char * argv[]) {
    if( 3 != argc ) {
        goto emExit;
    }
    const int pauseLength = strtoi( argv[2] );
    if(!strcmp("noreport", argv[1])) {
        // ...
    } else if(!strcmp("events", argv[1])) {
        // ...
    } else if(!strcmp("files", argv[1])) {
        // ...
    }
    return EXIT_SUCCESS;
emExit:
    fprintf( stderr, "Wrong number of command line arguments.\n" );
    print_usage( argv[0], stderr );
    return EXIT_FAILURE;
}

