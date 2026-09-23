#define _GNU_SOURCE

#include <fcntl.h>
#include <unistd.h>

extern char **environ;

int main(void) {
    char *arguments[] = {"true", NULL};
    execveat(AT_FDCWD, "/usr/bin/true", arguments, environ, 0);
    return 127;
}
