"""
A basic script to automate navigation of MLOL websites using a Selenium web driver (Firefox by default)
"""
from enum import Enum
import json
import logging
import os
import re
import string
import sys

from datetime import date, datetime, timedelta
from math import floor
from typing import List, Set
from urllib.parse import urlparse, quote_plus, parse_qs

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.expected_conditions import (
    invisibility_of_element)
from selenium.webdriver.support.ui import WebDriverWait  


class MLOLBookStatus(Enum):
  Available = 2
  Borrowed = 5
  BorrowedByMe = 3
  NotAvailable = 1
  Reserved = 4


MLOL_ACTIONS = {
  "SCARICA EBOOK": MLOLBookStatus.Available,
  "OCCUPATO": MLOLBookStatus.Borrowed,
  "RIPETI IL DOWNLOAD": MLOLBookStatus.BorrowedByMe,
  "NON DISPONIBILE\nPER LA TUA BIBLIOTECA": MLOLBookStatus.NotAvailable,
  "PRENOTATO": MLOLBookStatus.Reserved
}


class MLOLEntity:

  def __init__(self, id: int = None, name: str = None) -> None:
      self.id = id
      self.name = name

  def __str__(self) -> str:
      return self.name


class MLOLAuthor(MLOLEntity):
  pass


class MLOLPublisher(MLOLEntity):
  pass


class MLOLTopic(MLOLEntity):
  pass


class MLOLBook:

  def __init__(self, id: int = None, title: str = None, authors: List[MLOLAuthor] = (), cover: str = None, url: str = None, format: str = None, 
  publisher: MLOLPublisher = None, publication_date: date = None, description: str = None, isbn: List[str] = (), language: str = None, 
  topics: List[MLOLTopic] = (), status: Set[MLOLBookStatus] = (), is_favourite: bool = False) -> None:
      self.id = id
      self.title = title
      self.authors = authors
      self.cover = cover
      self.url = url
      self.format = format
      self.publisher = publisher
      self.publication_date = publication_date
      self.descrition = description
      self.isbn = isbn
      self.language = language
      self.topics = topics
      self.status = status
      self.is_favourite = is_favourite

  def __str__(self) -> str:
      authors = ", ".join([str(author) for author in self.authors])
      return f"[{authors}] {self.title}"


class MLOLReservation:

  def __init__(self, title: string, authors: str, queue_position: int, available_copies: int) -> None:
    self.title = title
    self.authors = authors
    self.queue_position = queue_position
    self.available_copies = available_copies
  
  def __str__(self) -> str:
      return str(self.__dict__)


class MLOLLoan:

  def __init__(self, title: str, authors: str, start_date: date, end_date: date) -> None:
      self.title = title
      self.authors = authors
      self.start_date = start_date
      self.end_date = end_date

  def __str__(self) -> str:
      return str(self.__dict__)


class MLOLConfig:

  QUANTITY_REGEX = re.compile('\d+')

  def __init__(self, base_url: str, username: str, password: str, max_concurrent_reservations: int, loan_duration_in_days: int, max_monthly_loans: int) -> None:
      self.current_month = date.today().month
      self.current_year = date.today().year
      self.base_url = base_url if base_url[-1] != "/" else base_url[:-1]
      self.username = username
      self.password = password
      assert max_concurrent_reservations > 0, "The maximum number of concurrent reservations must be greater than zero"
      self.max_concurrent_reservations = max_concurrent_reservations
      assert loan_duration_in_days > 0, "Duration of a loan (in days) must be greater than zero"
      self.loan_duration_in_days = loan_duration_in_days
      self.max_monthly_loans = max_monthly_loans


class MLOLClient:

  def __init__(self, config: MLOLConfig):
    self.config = config
    self.driver = webdriver.Firefox()

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    if exc_type or exc_value or traceback:
      logging.warning(f"Exiting context with a '{exc_type}' exception: {exc_value}")
    self.driver.close()
    return self

  def close(self):
    """
    Terminate the instance of the web driver instance currently used.
    
    NOTE: we recommend instantiating this class using a `with` statement, 
    since the close operation is performed automatically when going out of scope.  
    """
    self.driver.close()

  def __close_dialogs(self):
    wait=WebDriverWait(self.driver,5)
    try:
      dialogs = self.driver.find_elements_by_css_selector('.modal-dialog')
      for diag in dialogs:
        diag.find_element_by_css_selector('button[data-dismiss="modal"]').click()
        wait.until(invisibility_of_element(diag))
    except Exception as e:
      logging.exception(e)

  def login(self):
    self.driver.get(self.config.base_url)
    # Accept cookie policy
    self.driver.find_element_by_css_selector('a[onclick="acceptCookies()"]').click()
    # Fill username field
    username_field = self.driver.find_element_by_id("lusername")
    username_field.clear()
    username_field.send_keys(self.config.username)
    # Fill password field
    password_field = self.driver.find_element_by_id("lpassword")
    password_field.clear()
    password_field.send_keys(self.config.password)
    # Submit form
    self.driver.find_element_by_css_selector("#btnLogin > input").click()
    logging.info("Login request submitted")
    self.__close_dialogs()
  
  def get_active_loans(self) -> List[MLOLLoan]:
    self.driver.get(self.config.base_url + "/user/risorse.aspx#mlolloan")
    self.driver.find_element_by_css_selector('a[href="#mlolloan"]').click()
    active_loans = []
    for entry in self.driver.find_elements_by_css_selector("#mlolloan .bottom-buffer"):
      book_title = entry.find_element_by_css_selector("h3").text
      book_authors = entry.find_element_by_css_selector('span[itemprop="author"]').text
      loan_start = entry.find_element_by_css_selector('table tr:first-of-type td:nth-child(2) b').text
      loan_end = entry.find_element_by_css_selector('table tr:nth-child(2) td:nth-child(2) b').text
      active_loan = MLOLLoan(
        title=book_title, 
        authors=book_authors,
        start_date=datetime.strptime(loan_start, '%d/%m/%Y'),
        end_date=datetime.strptime(loan_end, '%d/%m/%Y')
      )
      logging.debug("Found an active loan: %s", active_loan)
      active_loans.append(active_loan)
    logging.info("Found %d active loan(s)", len(active_loans))
    return active_loans

  def get_all_loans(self) -> List[MLOLLoan]:
    self.driver.get(self.config.base_url + "/user/risorse.aspx#mlolloanhistory")
    self.driver.find_element_by_css_selector('a[href="#mlolloanhistory"]').click()
    loans = []
    for entry in self.driver.find_elements_by_css_selector("#mlolloanhistory .bottom-buffer"):
      book_title = entry.find_element_by_css_selector("h3").text
      book_authors = entry.find_element_by_css_selector('span[itemprop="author"]').text
      loan_start = entry.find_element_by_css_selector('table tr:first-of-type td:nth-child(2) b').text
      loan_end = entry.find_element_by_css_selector('table tr:nth-child(2) td:nth-child(2) b').text
      loan = MLOLLoan(
        title=book_title, 
        authors=book_authors, 
        start_date=datetime.strptime(loan_start, '%d/%m/%Y'), 
        end_date=datetime.strptime(loan_end, '%d/%m/%Y')
      )
      logging.debug("Found a loan: %s", loan)
      loans.append(loan)
    logging.info("Found %d loan(s)", len(loans))
    return loans

  def get_reservations(self) -> List[MLOLReservation]:
    self.driver.get(self.config.base_url + "/user/risorse.aspx#mlolreservation")
    self.driver.find_element_by_css_selector('a[href="#mlolreservation"]').click()
    reservations = []
    for entry in self.driver.find_elements_by_css_selector("#mlolreservation .bottom-buffer"):
      try:
        book_title = entry.find_element_by_css_selector("h3").text
        book_authors = entry.find_element_by_css_selector('span[itemprop="author"]').text
        entry.find_element_by_css_selector('div[id^="divPos"] .btn').click()
        # TODO Wait for the click to have effect and reservation details are actually loaded
        queue = entry.find_element_by_css_selector('div[id^="divPos"]')
        queue_position_msg, available_copies_msg = queue.text.split("\n")
        queue_position = self.config.QUANTITY_REGEX.match(queue_position_msg).group()
        available_copies = self.config.QUANTITY_REGEX.match(available_copies_msg).group()
        reservation = MLOLReservation(
          title=book_title, 
          authors=book_authors, 
          queue_position=int(queue_position), 
          available_copies=int(available_copies)
        )
        logging.debug("Found a reservation: %s", reservation)
        reservations.append(reservation)
      except Exception as ex:
        logging.exception(ex)
    logging.info("Found %d reservation(s)", len(reservations))
    return reservations

  def get_monthly_report(self) -> dict:
    all_loans = client.get_all_loans()
    current_month_loans = list(filter(lambda l: l.start_date.month == self.config.current_month and l.start_date.year == self.config.current_year, all_loans))
    logging.info(f"This month you are using {len(current_month_loans)}/{config.max_monthly_loans} loans")
    reservations = client.get_reservations()
    logging.info(f"You are using {len(reservations)}/{config.max_concurrent_reservations} reservations")
    return {
      'loans': {'used': len(current_month_loans), 'total': config.max_monthly_loans, 'available': config.max_monthly_loans-len(current_month_loans), 'list': current_month_loans},
      'reservations': {'used': len(reservations), 'total': self.config.max_concurrent_reservations, 'available': self.config.max_concurrent_reservations - len(reservations), 'list': reservations}
    }

  def search_books(self, query: str) -> List[MLOLBook]:
    current_page = 1
    self.driver.get(f"{self.config.base_url}/media/ricerca.aspx?keywords={quote_plus(query.strip())}&seltip=310&page={current_page}")
    results_count = int(self.driver.find_element_by_css_selector(".mlol.active span").text)
    logging.info(f"Found {results_count} result(s) for query '{query.strip()}'")
    books = []
    while True:
      logging.info(f"Getting results from page {current_page}")
      for result in self.driver.find_elements_by_css_selector('.ml-book-search-result.hidden-xs *[itemtype="http://schema.org/Book"]'):
        title = result.find_element_by_css_selector('*[itemprop="name"]').text
        url = result.find_element_by_css_selector('*[itemprop="url"]').get_attribute("href")
        id = int(parse_qs(urlparse(url).query)['id'][0])
        authors = []
        for author in result.find_elements_by_css_selector('[itemprop="author"] a.authorref'):
          author_id =  int(parse_qs(urlparse(author.get_attribute('href')).query)['selcrea'][0])
          author_name = author.text
          authors.append(MLOLAuthor(author_id, author_name))
        cover = result.find_element_by_css_selector('*[itemprop="image"]').value_of_css_property("background-image")[5:-2]   
        book = MLOLBook(id=id, title=title, authors=authors, cover=cover, url=url)
        books.append(book)
        logging.info(book)
      try:
        self.driver.find_element_by_css_selector('#pager a.page-link.next')
        next_page = current_page + 1
        self.driver.get(f"{self.config.base_url}/media/ricerca.aspx?keywords={quote_plus(query.strip())}&seltip=310&page={next_page}")
        current_page = next_page
      except NoSuchElementException as ex:
        logging.info("No other results page available, returning books")
        break
    return books

  def get_favourites(self):
    raise NotImplementedError()

  def get_book_details(self, id: int):
    assert isinstance(id, int) and id >= 0, "Book ID must be a positive integer"
    self.driver.get(f"{self.config.base_url}/media/scheda.aspx?id={id}")
    book = self.driver.find_element_by_css_selector('[itemtype="http://schema.org/Book"]')
    format = book.find_element_by_css_selector('[itemprop="bookFormat"]').get_attribute('content')
    cover = book.find_element_by_css_selector('[itemprop="image"]').get_attribute('src')
    title = book.find_element_by_css_selector('[itemprop="name"]').text
    authors = []
    for author in book.find_elements_by_css_selector('[itemprop="author"] a.authorref'):
      author_id =  int(parse_qs(urlparse(author.get_attribute('href')).query)['selcrea'][0])
      author_name = author.text
      authors.append(MLOLAuthor(author_id, author_name))
    publisher_element = book.find_element_by_css_selector('[itemprop="publisher"] a')
    publisher = MLOLPublisher(
      id=int(parse_qs(urlparse(publisher_element.get_attribute('href')).query)['selpub'][0]),
      name = publisher_element.text
    )
    publication_date = datetime.strptime(book.find_element_by_css_selector('meta[itemprop="datePublished"]').get_attribute('content'), '%d/%m/%Y')
    description = book.find_element_by_css_selector('[itemprop="description"]').text
    isbn = [isbn.text for isbn in book.find_elements_by_css_selector('[itemprop="isbn"]')]
    language = book.find_element_by_css_selector('[itemprop="inLanguage"]').text
    topics = []
    for topic in book.find_elements_by_css_selector('[itemprop="keywords"] a'):
      topics.append(MLOLTopic(
        id=int(parse_qs(urlparse(topic.get_attribute('href')).query)['idcce'][0]),
        name=topic.text
      ))
    actions = self.driver.find_elements_by_css_selector('.panel-mlol-body.open-mlol-actions a')
    status_flags = set()
    for action in actions:
      if action.text in MLOL_ACTIONS:
        status_flags.add(MLOL_ACTIONS[action.text])
    favourite_btn = self.driver.find_element_by_css_selector('.addtofavourite').text
    is_favourite = "Aggiunto ai preferiti" in favourite_btn
    return MLOLBook(
      id=id,
      cover=cover,
      title=title,
      format=format,
      authors=authors,
      publisher=publisher,
      publication_date=publication_date,
      description=description,
      isbn=isbn,
      language=language,
      topics=topics,
      status=status_flags,
      is_favourite=is_favourite
    )


if __name__ == "__main__":
  # execute only if run as a script
  logging.basicConfig(level=logging.INFO)

  assert len(sys.argv) == 2, "Missing argument for configuration file"
  config_path = os.path.abspath(sys.argv[1])
  assert os.path.isfile(config_path), "Configuration file not found or accessible"
  config = json.load(open(config_path))

  config = MLOLConfig(
    base_url=config['url'], 
    username=config['user.name'], 
    password=config['user.password'],
    max_concurrent_reservations=config['reservations.max_concurrent'],
    loan_duration_in_days=config['loans.duration_in_days'],
    max_monthly_loans=config['loans.max_monthly']
  )

  with MLOLClient(config) as client:
    client.login()
    client.get_book_details(150233380)
    client.get_book_details(150037804)
    client.get_book_details(150140586)
    client.get_book_details(150228397)
    client.get_book_details(150183928)
    monthly_report = client.get_monthly_report()
    for reservation in monthly_report['reservations']['list']:
      people_ahead_in_queue = reservation.queue_position - 1
      rounds_to_wait = floor(people_ahead_in_queue / reservation.available_copies)
      # Best scenario: tomorrow all copies will be available for the next people in the queue
      days_to_wait = 1 + rounds_to_wait * config.loan_duration_in_days
      best_availability = date.today() + timedelta(days=1) + timedelta(days=days_to_wait)
      # Worst scenario: all copies were taken today and they will be available for the next people in the queue after this "round"
      days_to_wait = (rounds_to_wait + 1) * config.loan_duration_in_days
      worst_availability = date.today() + timedelta(days=1) + timedelta(days=days_to_wait)
      logging.info(f"'{reservation.title}' by '{reservation.authors}' should be available between {best_availability} and {worst_availability}")
