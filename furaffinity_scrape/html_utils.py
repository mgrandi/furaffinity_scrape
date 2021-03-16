import logging
import re
import typing

from furaffinity_scrape import utils
from furaffinity_scrape import constants

logger = logging.getLogger(__name__)


def extract_username_from_url(url, warn_on_mismatch=True) -> typing.Optional[str]:
    '''
    get the username from urls that could appear

    such as relative or full username urls

    @param url - the url to check against our regexes
    @param warn_on_mismatch - if true, we will warn if the url
    didn't match any of the regexes
    @return a username that was found in the url or None if nothing was found

    '''

    possible_regexes = [constants.FURAFFINITY_RELATIVE_USERNAME_RE, constants.FURAFFINITY_USERNAME_RE]

    for iter_regex in possible_regexes:
        search_result = iter_regex.search(url)
        logger.debug("extract_username_from_url: seeing if `%s` matches the regex `%s`, result: `%s`",
            url, iter_regex, search_result)

        if search_result is not None:

                return search_result.groupdict()[constants.RELATIVE_URL_RE_KEY]

    # if we get here then none of the regexes matched
    if warn_on_mismatch:
        logger.warning("extract_username_from_url: url `%s` did not match against any of the regexes `%s`",
            url, possible_regexes)
        return None
    else:
        return None

def get_artist_username_as_list(soup):
    result_list = utils.make_soup_query_and_validate_number(
        soup=soup,
        query="div.submission-id-avatar > a",
        number_of_elements_expected=1)


    artist_avatar_link = result_list[0]["href"]

    artist_username = extract_username_from_url(artist_avatar_link)
    if not artist_username:
        # if we get here, there are characters we didn't know about that we aren't handling
        logger.error("didn't get a result from extract_username_from_url for the artist name from the element `%s`, this is a bug", artist_avatar_link)
        raise Exception(f"didn't get a result from extract_username_from_url for the artist name from the element `{artist_avatar_link}`, this is a bug")

    return [artist_username]

def get_commenter_usernames_as_list(soup):


    result_list = utils.make_soup_query_and_validate_number(
        soup=soup,
        query="strong.comment_username > h3",
        number_of_elements_expected=-1)

    return [iter_element.text.strip().lower() for iter_element in result_list]


def _submission_description_usernames_by_a_tag_class(soup, class_to_search_for, warn_on_mismatch=True):
    '''
    finds usernames that are in an <a> tag that has a specific class

    @param soup - the beautiful soup object
    @param class_to_search_for - the str html class to search for
    @param warn_on_mismatch - if true, this will warn if we didn't find
    any usernames in the url

    @param a list of usernames
    '''

    result_list = utils.make_soup_query_and_validate_number(
        soup=soup,
        query=f"a.{class_to_search_for}",
        number_of_elements_expected=-1)

    results = []

    for iter_element in result_list:
        raw_href = iter_element["href"]

        maybe_username = extract_username_from_url(raw_href, warn_on_mismatch)
        if maybe_username:
            results.append(maybe_username)

    return results

def get_submission_description_avatar_usernames_as_list(soup):
    '''
    finds usernames that are in the submission description that are an clickable
    image (the user avatar) to the users profile (aka `:iconUSERNAME:`)

    see https://www.furaffinity.net/help#uploads-and-submissions

    like this:

    <a class="iconusername" href="/user/lazydez">
        <img align="middle" alt="lazydez" src="//a.furaffinity.net/20210313/lazydez.gif" title="lazydez"> lazydez
        </img>
    </a>
    '''

    return _submission_description_usernames_by_a_tag_class(soup, "iconusername")

def get_submission_description_link_usernames_as_list(soup):
    '''
    finds usernames that are in the submission description that are an clickable
    link to the user's profile (aka `:linkUSERNAME:`)

    see https://www.furaffinity.net/help#uploads-and-submissions

    like this:

    <a class="linkusername" href="/user/craid">Craid</a>
    '''

    return _submission_description_usernames_by_a_tag_class(soup, "linkusername")

def get_submission_description_autolink_usernames_as_list(soup):
    '''
    find usernames that are in the submission description, that are normal urls
    (aka `[url=example.com]something[/url]` )

    like this:

    <a
        class="auto_link"
        href="https://www.furaffinity.net/user/chaoman16/"
        title="https://www.furaffinity.net/user/chaoman16/">www.furaffinity.net/user/chaoman16/
    </a>
    '''

    possible_urls = _submission_description_usernames_by_a_tag_class(
        soup, "auto_link", warn_on_mismatch=False)

    return possible_urls








