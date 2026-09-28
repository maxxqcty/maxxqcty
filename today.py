import re
import requests
import os
from lxml import etree
import time
import hashlib
import math

# Fine-grained personal access token with All Repositories access:
# Account permissions: read:Followers, read:Starring, read:Watching
# Repository permissions: read:Commit statuses, read:Contents, read:Issues, read:Metadata, read:Pull Requests
# Issues and pull requests permissions not needed at the moment, but may be used in the future
HEADERS = {'authorization': 'token '+ os.environ['ACCESS_TOKEN']}
USER_NAME = 'maxxqcty'  # your GitHub username
QUERY_COUNT = {'user_getter': 0, 'follower_getter': 0, 'graph_repos_stars': 0, 'recursive_loc': 0, 'graph_commits': 0, 'loc_query': 0, 'language_fetch': 0}


CACHE_LINE_PATTERN = re.compile(r'^[0-9a-f]{64}\s+\d+\s+\d+\s+\d+\s+\d+\s*$')


def cache_comment_size(lines):
    """
    Returns the number of leading comment lines in a cache file:
    everything before the first line matching the cache data format
    (64-char repo hash, then 4 integers), e.g. 7 for the template's
    header block, or len(lines) if the file holds no data yet.
    """
    for index, line in enumerate(lines):
        if CACHE_LINE_PATTERN.match(line):
            return index
    return len(lines)


MAX_ATTEMPTS = 3
RETRYABLE_STATUSES = (403, 429, 500, 502, 503, 504)


def simple_request(func_name, query, variables):
    """
    Returns a request, or raises an Exception if the response does not succeed.
    Retries transient failures (GitHub's non-documented 403 abuse limit, rate
    limits and 5xx) up to MAX_ATTEMPTS times with exponential backoff, and
    treats a 200 response carrying a GraphQL `errors` payload as a failure
    (GitHub reports query failures with HTTP 200).
    """
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables':variables}, headers=HEADERS)
        if request.status_code == 200:
            payload = request.json()
            if isinstance(payload, dict) and payload.get('errors'):
                last_error = f'GraphQL error in {func_name}: {payload["errors"]}'
            else:
                return request
        elif request.status_code in RETRYABLE_STATUSES:
            last_error = (func_name, ' has failed with a', request.status_code, request.text, QUERY_COUNT)
        else:
            raise Exception(func_name, ' has failed with a', request.status_code, request.text, QUERY_COUNT)
        if attempt < MAX_ATTEMPTS:
            time.sleep(2 ** (attempt - 1)) # exponential backoff: 1s, 2s
    if isinstance(last_error, str):
        raise Exception(last_error)
    raise Exception(*last_error)


def graph_commits(start_date, end_date):
    """
    Uses GitHub's GraphQL v4 API to return my total commit count
    """
    query_count('graph_commits')
    query = '''
    query($start_date: DateTime!, $end_date: DateTime!, $login: String!) {
        user(login: $login) {
            contributionsCollection(from: $start_date, to: $end_date) {
                contributionCalendar {
                    totalContributions
                }
            }
        }
    }'''
    variables = {'start_date': start_date,'end_date': end_date, 'login': USER_NAME}
    request = simple_request(graph_commits.__name__, query, variables)
    return int(request.json()['data']['user']['contributionsCollection']['contributionCalendar']['totalContributions'])


def graph_repos_stars(count_type, owner_affiliation, cursor=None, edges=None):
    """
    Uses GitHub's GraphQL v4 API to return my total repository, star, or lines of code count.
    Star counts are summed over every page of repositories (100 at a time); the
    repository count comes from totalCount, which is already the full count.
    """
    if edges is None:
        edges = []
    query_count('graph_repos_stars')
    query = '''
    query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 100, after: $cursor, ownerAffiliations: $owner_affiliation) {
                totalCount
                edges {
                    node {
                        ... on Repository {
                            nameWithOwner
                            stargazerCount
                        }
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    }'''
    variables = {'owner_affiliation': owner_affiliation, 'login': USER_NAME, 'cursor': cursor}
    request = simple_request(graph_repos_stars.__name__, query, variables)
    repositories = request.json()['data']['user']['repositories']
    if count_type == 'repos':
        return repositories['totalCount'] # totalCount covers every page already
    edges += repositories['edges']
    if repositories['pageInfo']['hasNextPage']:
        return graph_repos_stars(count_type, owner_affiliation, repositories['pageInfo']['endCursor'], edges)
    if count_type == 'stars':
        return stars_counter(edges)
    raise ValueError(f'unknown count_type {count_type!r}')


def recursive_loc(owner, repo_name, data, cache_comment):
    """
    Uses GitHub's GraphQL v4 API and cursor pagination to fetch 100 commits from a repository at a time
    Iterates instead of recursing, so repositories with hundreds of thousands of
    commits cannot overflow the stack
    """
    query = '''
    query ($repo_name: String!, $owner: String!, $cursor: String) {
        repository(name: $repo_name, owner: $owner) {
            defaultBranchRef {
                target {
                    ... on Commit {
                        history(first: 100, after: $cursor) {
                            totalCount
                            edges {
                                node {
                                    ... on Commit {
                                        committedDate
                                    }
                                    author {
                                        user {
                                            id
                                        }
                                    }
                                    deletions
                                    additions
                                }
                            }
                            pageInfo {
                                endCursor
                                hasNextPage
                            }
                        }
                    }
                }
            }
        }
    }'''
    addition_total, deletion_total, my_commits, cursor = 0, 0, 0, None
    while True:
        query_count('recursive_loc')
        variables = {'repo_name': repo_name, 'owner': owner, 'cursor': cursor}
        request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables':variables}, headers=HEADERS) # I cannot use simple_request(), because I want to save the file before raising Exception
        if request.status_code != 200:
            force_close_file(data, cache_comment) # saves what is currently in the file before this program crashes
            if request.status_code == 403:
                raise Exception('Too many requests in a short amount of time!\nYou\'ve hit the non-documented anti-abuse limit!')
            raise Exception('recursive_loc() has failed with a', request.status_code, request.text, QUERY_COUNT)
        repository = request.json()['data']['repository']
        if repository['defaultBranchRef'] is None:
            return 0 # The repo is empty
        history = repository['defaultBranchRef']['target']['history']
        # only adds the LOC value of commits authored by me
        for node in history['edges']:
            if node['node']['author']['user'] == OWNER_ID:
                my_commits += 1
                addition_total += node['node']['additions']
                deletion_total += node['node']['deletions']
        if not history['pageInfo']['hasNextPage']:
            return addition_total, deletion_total, my_commits
        cursor = history['pageInfo']['endCursor']


def loc_query(owner_affiliation, force_cache=False, cursor=None, edges=None):
    """
    Uses GitHub's GraphQL v4 API to query all the repositories I have access to (with respect to owner_affiliation)
    Queries 60 repos at a time, because larger queries give a 502 timeout error and smaller queries send too many
    requests and also give a 502 error.
    Returns the total number of lines of code in all repositories
    """
    if edges is None:
        edges = []
    query_count('loc_query')
    query = '''
    query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 60, after: $cursor, ownerAffiliations: $owner_affiliation) {
            edges {
                node {
                    ... on Repository {
                        nameWithOwner
                        defaultBranchRef {
                            target {
                                ... on Commit {
                                    history {
                                        totalCount
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    }'''
    variables = {'owner_affiliation': owner_affiliation, 'login': USER_NAME, 'cursor': cursor}
    request = simple_request(loc_query.__name__, query, variables)
    if request.json()['data']['user']['repositories']['pageInfo']['hasNextPage']:   # If repository data has another page
        edges += request.json()['data']['user']['repositories']['edges']            # Add on to the LoC count
        return loc_query(owner_affiliation, force_cache, request.json()['data']['user']['repositories']['pageInfo']['endCursor'], edges)
    else:
        return cache_builder(edges + request.json()['data']['user']['repositories']['edges'], force_cache)


def cache_filename():
    """
    Returns this user's cache file path; the username is hashed so no
    filename leaks the account name
    """
    return 'cache/'+hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest()+'.txt'


def cache_builder(edges, force_cache=False, filename=None, loc_add=0, loc_del=0):
    """
    Checks each repository in edges to see if it has been updated since the last time it was cached
    If it has, run recursive_loc on that repository to update the LOC count
    The comment block at the top of the cache file is detected automatically
    """
    cached = True # Assume all repositories are cached
    if filename is None:
        filename = cache_filename()
    try:
        with open(filename, 'r') as f:
            data = f.readlines()
    except FileNotFoundError: # If the cache file doesn't exist, create it
        data = []
        with open(filename, 'w') as f:
            f.writelines(data)

    comment_size = cache_comment_size(data)
    if len(data)-comment_size != len(edges) or force_cache: # If the number of repos has changed, or force_cache is True
        cached = False
        flush_cache(edges, filename)
        with open(filename, 'r') as f:
            data = f.readlines()
        comment_size = cache_comment_size(data)

    cache_comment = data[:comment_size] # save the comment block
    data = data[comment_size:] # remove those lines
    for index in range(len(edges)):
        repo_hash, commit_count, *__ = data[index].split()
        if repo_hash == hashlib.sha256(edges[index]['node']['nameWithOwner'].encode('utf-8')).hexdigest():
            try:
                if int(commit_count) != edges[index]['node']['defaultBranchRef']['target']['history']['totalCount']:
                    # if commit count has changed, update loc for that repo
                    owner, repo_name = edges[index]['node']['nameWithOwner'].split('/')
                    loc = recursive_loc(owner, repo_name, data, cache_comment)
                    data[index] = repo_hash + ' ' + str(edges[index]['node']['defaultBranchRef']['target']['history']['totalCount']) + ' ' + str(loc[2]) + ' ' + str(loc[0]) + ' ' + str(loc[1]) + '\n'
            except TypeError: # If the repo is empty
                data[index] = repo_hash + ' 0 0 0 0\n'
    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    for line in data:
        loc = line.split()
        loc_add += int(loc[3])
        loc_del += int(loc[4])
    return [loc_add, loc_del, loc_add - loc_del, cached]


def flush_cache(edges, filename):
    """
    Rebuilds the cache file so it lists exactly `edges`.
    The comment block and the data of repositories still present are preserved
    (matched by repo hash), so adding or removing a repository does not force a
    re-walk of every commit; only brand-new repositories start zeroed.
    """
    try:
        with open(filename, 'r') as f:
            old_lines = f.readlines()
    except FileNotFoundError:
        old_lines = []
    comment_size = cache_comment_size(old_lines)
    old_by_hash = {line.split()[0]: line for line in old_lines[comment_size:] if line.split()}
    with open(filename, 'w') as f:
        f.writelines(old_lines[:comment_size])
        for node in edges:
            repo_hash = hashlib.sha256(node['node']['nameWithOwner'].encode('utf-8')).hexdigest()
            f.write(old_by_hash.get(repo_hash, repo_hash + ' 0 0 0 0\n'))


def force_close_file(data, cache_comment):
    """
    Forces the file to close, preserving whatever data was written to it
    This is needed because if this function is called, the program would've crashed before the file is properly saved and closed
    """
    filename = 'cache/'+hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest()+'.txt'
    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    print('There was an error while writing to the cache file. The file,', filename, 'has had the partial data saved and closed.')


def stars_counter(data):
    """
    Count total stars in repositories owned by me
    """
    total_stars = 0
    for node in data: total_stars += node['node']['stargazerCount']
    return total_stars


def svg_overwrite(filename, commit_data, star_data, repo_data, contrib_data, follower_data, loc_data):
    """
    Parse SVG files and update elements with my commits, stars, repositories, and lines written
    """
    tree = etree.parse(filename)
    root = tree.getroot()
    justify_format(root, 'commit_data', commit_data, 22)
    justify_format(root, 'star_data', star_data, 14)
    justify_format(root, 'repo_data', repo_data, 6)
    justify_format(root, 'contrib_data', contrib_data)
    justify_format(root, 'follower_data', follower_data, 10)
    justify_format(root, 'loc_data', loc_data[2], 9)
    justify_format(root, 'loc_add', loc_data[0])
    justify_format(root, 'loc_del', loc_data[1], 7)
    tree.write(filename, encoding='utf-8', xml_declaration=True)


def justify_format(root, element_id, new_text, length=0):
    """
    Updates and formats the text of the element, and modifes the amount of dots in the previous element to justify the new text on the svg
    """
    if isinstance(new_text, int):
        new_text = f"{'{:,}'.format(new_text)}"
    new_text = str(new_text)
    find_and_replace(root, element_id, new_text)
    just_len = max(0, length - len(new_text))
    if just_len <= 2:
        dot_map = {0: '', 1: ' ', 2: '. '}
        dot_string = dot_map[just_len]
    else:
        dot_string = ' ' + ('.' * just_len) + ' '
    find_and_replace(root, f"{element_id}_dots", dot_string, required=False)


def find_and_replace(root, element_id, new_text, required=True):
    """
    Finds the element in the SVG file and replaces its text with a new value.
    Raises KeyError if the id is missing and required is True (a renamed or
    removed element should fail the build, not silently render stale stats);
    optional ids (the decorative dot fillers) are skipped.
    """
    element = root.find(f".//*[@id='{element_id}']")
    if element is None:
        if required:
            raise KeyError(f'no element with id={element_id!r} in the SVG')
        return
    element.text = new_text


LANG_THEMES = {
    'dark': {'bg': '#161b22', 'title': '#e6edf3', 'label': '#e6edf3', 'pct': '#8b98ac'},
    'light': {'bg': '#f6f8fa', 'title': '#24292f', 'label': '#24292f', 'pct': '#8494ab'},
}
LANG_OTHER_COLOR = '#8b949e'


def language_fetch():
    """
    Returns [(name, bytes, linguist color)] for the account's public, non-fork
    repositories, aggregated by bytes and sorted largest first.
    """
    query_count('language_fetch')
    query = '''
    query ($login: String!) {
        user(login: $login) {
            repositories(first: 100, ownerAffiliations: [OWNER]) {
                pageInfo { hasNextPage }
                nodes {
                    isFork
                    isPrivate
                    languages(first: 100, orderBy: {field: SIZE, direction: DESC}) {
                        edges { size node { name color } }
                    }
                }
            }
        }
    }'''
    variables = {'login': USER_NAME}
    request = simple_request(language_fetch.__name__, query, variables)
    repository_page = request.json()['data']['user']['repositories']
    if repository_page['pageInfo']['hasNextPage']:
        raise Exception('language_fetch: more than 100 repositories, language totals would be incomplete')
    totals, colors = {}, {}
    for repository in repository_page['nodes']:
        if repository['isFork'] or repository['isPrivate']:
            continue
        for edge in repository['languages']['edges']:
            name = edge['node']['name']
            totals[name] = totals.get(name, 0) + edge['size']
            if edge['node'].get('color') and name not in colors:
                colors[name] = edge['node']['color']
    if not totals:
        raise ValueError('language_fetch found no languages in the public non-fork repositories')
    ranked = sorted(totals, key=lambda name: -totals[name])
    return [(name, totals[name], colors.get(name, LANG_OTHER_COLOR)) for name in ranked]


def language_render(entries, theme, top=6):
    """
    Renders the compact language pie card as an SVG string: the `top` largest
    languages plus an aggregate Other slice, a legend, and a title.
    Pure and deterministic for identical input, so unchanged language data
    produces an unchanged file and no bot commit.
    """
    palette = LANG_THEMES[theme]
    total = sum(size for _, size, _ in entries)
    if total <= 0:
        raise ValueError('language_render: total byte count must be positive')
    slices = list(entries[:top])
    if len(entries) > top:
        slices.append(('Other', sum(size for _, size, _ in entries[top:]), LANG_OTHER_COLOR))
    width, height = 420, 150
    center_x, center_y, radius = 78, 84, 55
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,monospace" width="{width}px" height="{height}px" font-size="11px">',
        f'<rect width="{width}px" height="{height}px" rx="15" fill="{palette["bg"]}"/>',
        f'<text x="22" y="20" font-size="13" fill="{palette["title"]}">Languages</text>',
    ]

    def slice_point(degrees):  # 0 degrees points at 12 o'clock, increasing clockwise
        radians = math.radians(degrees - 90)
        return center_x + radius * math.cos(radians), center_y + radius * math.sin(radians)

    start = 0.0
    for _, size, color in slices:
        sweep = 360 * size / total
        if sweep >= 359.99:
            lines.append(f'<circle cx="{center_x}" cy="{center_y}" r="{radius}" fill="{color}"/>')
        else:
            x_start, y_start = slice_point(start)
            x_end, y_end = slice_point(start + sweep)
            large_arc = int(sweep > 180)
            lines.append(
                f'<path d="M{center_x} {center_y}L{x_start:.4f} {y_start:.4f}'
                f'A{radius} {radius} 0 {large_arc} 1 {x_end:.4f} {y_end:.4f}Z"'
                f' fill="{color}" stroke="{palette["bg"]}" stroke-width="1"/>'
            )
        start += sweep

    for index, (name, size, color) in enumerate(slices):
        baseline = 46 + 16 * index
        lines.append(f'<rect x="155" y="{baseline - 8}" width="8" height="8" rx="2" fill="{color}"/>')
        lines.append(f'<text x="171" y="{baseline}" fill="{palette["label"]}">{name}</text>')
        lines.append(f'<text x="410" y="{baseline}" text-anchor="end" fill="{palette["pct"]}">{round(100 * size / total)}%</text>')

    lines.append('</svg>')
    return '\n'.join(lines) + '\n'


def commit_counter(filename=None):
    """
    Counts up my total commits, using the cache file created by cache_builder.
    The comment block at the top of the file is detected automatically.
    """
    if filename is None:
        filename = 'cache/'+hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest()+'.txt'
    with open(filename, 'r') as f:
        data = f.readlines()
    data = data[cache_comment_size(data):] # remove the comment block
    total_commits = 0
    for line in data:
        total_commits += int(line.split()[2])
    return total_commits


def user_getter(username):
    """
    Returns the account ID and creation time of the user
    """
    query_count('user_getter')
    query = '''
    query($login: String!){
        user(login: $login) {
            id
            createdAt
        }
    }'''
    variables = {'login': username}
    request = simple_request(user_getter.__name__, query, variables)
    return {'id': request.json()['data']['user']['id']}, request.json()['data']['user']['createdAt']

def follower_getter(username):
    """
    Returns the number of followers of the user
    """
    query_count('follower_getter')
    query = '''
    query($login: String!){
        user(login: $login) {
            followers {
                totalCount
            }
        }
    }'''
    request = simple_request(follower_getter.__name__, query, {'login': username})
    return int(request.json()['data']['user']['followers']['totalCount'])


def query_count(funct_id):
    """
    Counts how many times the GitHub GraphQL API is called
    """
    global QUERY_COUNT
    QUERY_COUNT[funct_id] += 1


def perf_counter(funct, *args):
    """
    Calculates the time it takes for a function to run
    Returns the function result and the time differential
    """
    start = time.perf_counter()
    funct_return = funct(*args)
    return funct_return, time.perf_counter() - start


def formatter(query_type, difference, funct_return=False, whitespace=0):
    """
    Prints a formatted time differential
    Returns formatted result if whitespace is specified, otherwise returns raw result
    """
    print('{:<23}'.format('   ' + query_type + ':'), sep='', end='')
    print('{:>12}'.format('%.4f' % difference + ' s ')) if difference > 1 else print('{:>12}'.format('%.4f' % (difference * 1000) + ' ms'))
    if whitespace:
        return f"{'{:,}'.format(funct_return): <{whitespace}}"
    return funct_return


def main():
    """
    Fetches every stat from the GitHub GraphQL API and writes the stats and language-card SVG variants.
    Andrew Grant (Andrew6rant) wrote the original, 2022-2025.
    """
    global OWNER_ID  # recursive_loc reads OWNER_ID as a module global
    print('Calculation times:')
    # fetch the account's node id (used to only count commits authored by me) and creation date
    user_data, user_time = perf_counter(user_getter, USER_NAME)
    OWNER_ID, acc_date = user_data
    formatter('account data', user_time)
    lang_data = language_fetch()
    total_loc, loc_time = perf_counter(loc_query, ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'])
    formatter('LOC (cached)', loc_time) if total_loc[-1] else formatter('LOC (no cache)', loc_time)
    commit_data, commit_time = perf_counter(commit_counter)
    star_data, star_time = perf_counter(graph_repos_stars, 'stars', ['OWNER'])
    repo_data, repo_time = perf_counter(graph_repos_stars, 'repos', ['OWNER'])
    contrib_data, contrib_time = perf_counter(graph_repos_stars, 'repos', ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'])
    follower_data, follower_time = perf_counter(follower_getter, USER_NAME)

    for index in range(len(total_loc)-1): total_loc[index] = '{:,}'.format(total_loc[index]) # format added, deleted, and total LOC

    svg_overwrite('dark_mode.svg', commit_data, star_data, repo_data, contrib_data, follower_data, total_loc[:-1])
    svg_overwrite('light_mode.svg', commit_data, star_data, repo_data, contrib_data, follower_data, total_loc[:-1])
    with open('languages_dark.svg', 'w', encoding='utf-8', newline='') as pie_file:
        pie_file.write(language_render(lang_data, 'dark'))
    with open('languages_light.svg', 'w', encoding='utf-8', newline='') as pie_file:
        pie_file.write(language_render(lang_data, 'light'))

    # move cursor to override 'Calculation times:' with 'Total function time:' and the total function time, then move cursor back
    print('\033[F\033[F\033[F\033[F\033[F\033[F\033[F\033[F',
        '{:<21}'.format('Total function time:'), '{:>11}'.format('%.4f' % (user_time + loc_time + commit_time + star_time + repo_time + contrib_time)),
        ' s \033[E\033[E\033[E\033[E\033[E\033[E\033[E\033[E', sep='')

    print('Total GitHub GraphQL API calls:', '{:>3}'.format(sum(QUERY_COUNT.values())))
    for funct_name, count in QUERY_COUNT.items(): print('{:<28}'.format('   ' + funct_name + ':'), '{:>6}'.format(count))


if __name__ == '__main__':
    main()