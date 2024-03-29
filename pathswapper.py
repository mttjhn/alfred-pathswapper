# encoding: utf-8

import sys
import subprocess
import os
import urllib
from workflow import Workflow3, ICON_NETWORK, ICON_HOME, ICON_WARNING

log = None
mountMap = None

# This function gets the current clipboard contents (in text)
def getClipboard():
    p = subprocess.Popen(["pbpaste"], stdout=subprocess.PIPE)
    p.wait()
    data = p.stdout.read()
    return data


def getNetworkFromMount(mountPath):
    log.debug(mountPath)
    df = subprocess.Popen(["df", mountPath], stdout=subprocess.PIPE)
    outputLine = df.stdout.readlines()[1]
    outputLine = outputLine.decode('ascii')
    log.debug(outputLine)
    uncPath = outputLine.split()[0]
    # Remove the user login info from the front
    serverPath = uncPath.split("@")[1].lower()
    return serverPath


def getMountFromNetwork(networkPath):
    log.debug(networkPath)
    df = subprocess.Popen(["df", "-T", "smbfs"], stdout=subprocess.PIPE)
    for m in df.stdout.readlines():
        mount = m.decode('ascii')
        # Skip the header line when parsing STDOUT
        if not mount.startswith("Filesystem"):
            uncPath = mount.split()[0]
            mountLoc = mount.split()[8]
            serverPath = uncPath.split("@")[1].lower()
            log.debug(serverPath)
            log.debug(mountLoc)
            if serverPath.lower() == networkPath.lower():
                return mountLoc
            else:
                networkSplit = networkPath.split("/")
                if len(networkSplit) == 2:
                    if (
                        networkSplit[0].lower() in serverPath.lower()
                        and networkSplit[1].lower() in serverPath.lower()
                    ):
                        return mountLoc


# This function converts Windows to SMB paths
def convertToSmb(winPath):
    # Assumes that winPath is something like '\\server\share'
    return "smb:" + flipForward(winPath)


# This function converts Windows to mounted Volumes
def convertToVolume(path, isSmb):
    output = None
    if isSmb:
        # Assumes that path is a SMB path
        splitPath = path[6:].split("/")
        server = splitPath[0]
        share = splitPath[1]
        networkPath = server + "/" + share
        log.debug(networkPath)
        mountPath = getMountFromNetwork(networkPath)
        # Check to see if the path is not null AND is mounted
        if mountPath and os.path.exists(mountPath):
            log.debug(mountPath)
            # Simplistic version here...
            output = flipForward(path[6:].replace(networkPath, mountPath))
    else:
        # Assumes that path is a Windows path, something like '\\server\share'
        # Start by parsing out the server and share
        splitPath = path[2:].split("\\")
        server = splitPath[0]
        share = splitPath[1]
        networkPath = server + "/" + share
        log.debug(networkPath)
        mountPath = getMountFromNetwork(networkPath)
        # Check to see if the path is not null AND is mounted
        if mountPath and os.path.exists(mountPath):
            log.debug(mountPath)
            # Simplistic version here...
            output = flipForward(path[2:]).replace(networkPath, mountPath)
            log.debug(output)

    return output


# This function converts from Mac to Windows Links
def convertToWindows(macPath, isSmb):
    output = None

    if isSmb:
        # Assumes we have a fully-qualified SMB link
        output = flipBack(macPath.replace("smb://", "//"))
    else:
        # Assumes we're starting with a classic /Volumes/ link
        splitPath = macPath[1:].split("/")
        share = splitPath[1].strip()
        mountLoc = "/" + splitPath[0] + "/" + share
        log.debug(share)
        log.debug(mountLoc)
        replace = None
        networkMnt = getNetworkFromMount(mountLoc + "/")
        replace = networkMnt
        # Let's see if we got anything
        # if networkMnt:
        #    replace = networkMnt
        # else:
        #    for s in mountMap:
        #        if s[0].lower() == share.lower():
        #            log.debug('Found loc!')
        #            replace = s[1]
        #            log.debug(replace)
        if replace is not None:
            output = flipBack("\\\\" + macPath.replace(mountLoc, replace))
    return output


# This function flips slashes to forward-slashes
def flipForward(input):
    return input.replace("\\", "/")


# This function flips slashes to back-slashes
def flipBack(input):
    return input.replace("/", "\\")


def main(wf):
    log.debug("Started!")
    # Get query from Alfred
    if len(wf.args):
        query = wf.args[0]
    else:
        query = None

    log.debug(query)
    # If the query is blank, grab the contents of the clipboard
    if query == None:
        query = getClipboard()
        query = query.decode('ascii')

    log.debug(query)

    if query is not None:
        # Start by trimming whitespace
        query = query.strip()
        optionsShown = False
        # Then, let's check the contents to see what we have
        # Check first for file:// and flip it if needed
        if query[:7] == "file://":
            log.debug("found file")
            query = urllib.unquote(query).decode("utf8")
            query = flipBack(query.replace("file:", ""))
            log.debug(query)
        # Now, let's go through the contents!
        if query[:2] == "\\\\":
            # We likely have a windows path!
            # TODO: Add modifiers for copying instead of opening, etc.
            smbPath = convertToSmb(query)
            volPath = convertToVolume(query, False)
            # Option to copy SMB Path
            smb = wf.add_item(
                title="Copy SMB Path...",
                subtitle=smbPath,
                arg=smbPath,
                icon=ICON_NETWORK,
                valid=True,
            )
            smb.setvar("copy", "1")
            optionsShown = True
            if volPath is not None:
                # Option to open path in Finder
                vol = wf.add_item(
                    title="Open in Finder...",
                    subtitle=volPath,
                    arg=volPath,
                    icon=ICON_NETWORK,
                    type="file",
                    valid=True,
                )
                vol.setvar("open", "1")
                # Option to Browse in Alfred
                brow = wf.add_item(
                    title="Browse in Alfred...",
                    subtitle=volPath,
                    arg=volPath,
                    icon=ICON_NETWORK,
                    type="file",
                    valid=True,
                )
                brow.setvar("browse", "1")
            log.debug("Windows Path found! Path: " + query)
        elif query is not None and query[:6] == "smb://":
            # We likely have a smb:// path
            volPath = convertToVolume(query, True)
            if volPath is not None:
                # Option to open path in Finder
                vol = wf.add_item(
                    title="Open in Finder...",
                    subtitle=volPath,
                    arg=volPath,
                    icon=ICON_NETWORK,
                    type="file",
                    valid=True,
                )
                vol.setvar("open", "1")
            # Check for windows path to copy
            winPath = convertToWindows(query, True)
            if winPath is not None:
                optionsShown = True
                # Option to copy path to clipboard
                win = wf.add_item(
                    title="Copy UNC/Windows Path...",
                    subtitle=winPath,
                    arg=winPath,
                    icon=ICON_NETWORK,
                    valid=True,
                )
                win.setvar("copy", "1")
            log.debug("SMB Path found! Path: " + query)
        elif query[:7] == "file://":
            # We have some form of File path. Let's see what we can do...
            wf.add_item(
                title="File Path!",
                subtitle="Need to look up more info...",
                icon=ICON_NETWORK,
            )
            log.debug("File Path found! Path: " + query)
        elif query is not None and query[:1] == "/":
            # We likely have a Mac Path
            # Check for mounted volumes here
            if query[:9] == "/Volumes/":
                winPath = convertToWindows(query, False)
                if winPath is not None:
                    optionsShown = True
                    # Option to copy path to clipboard
                    win = wf.add_item(
                        title="Copy UNC/Windows Path...",
                        subtitle=winPath,
                        arg=winPath,
                        icon=ICON_NETWORK,
                        valid=True,
                    )
                    win.setvar("copy", "1")
            log.debug("Mac Path found! Path: " + query)

    if not optionsShown:
        wf.add_item(
            title="Could not find a valid path in Clipboard...",
            subtitle="Try again...",
            icon=ICON_WARNING,
        )

    # Send the results to Alfred as XML
    wf.send_feedback()


if __name__ == "__main__":
    wf = Workflow3()
    log = wf.logger
    sys.exit(wf.run(main))
