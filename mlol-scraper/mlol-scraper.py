"""
Selenium vs requests scraping
https://milano.medialibrary.it/commons/QueuePos.aspx?id=1807109
"""
import json
import logging
import os
import re
import string
import sys

from collections import namedtuple
from datetime import date, datetime, timedelta
from math import floor
from typing import List

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.expected_conditions import \
    invisibility_of_element
from selenium.webdriver.support.ui import WebDriverWait

logging.basicConfig(level=logging.INFO)


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

  def close(self):
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

  def get_favourites(self):
    raise NotImplementedError()

  def get_book_details(self):
    raise NotImplementedError()

  def search_books(self, query: str):
    raise NotImplementedError()


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

client = MLOLClient(config)

client.login()

client.get_active_loans()

monthly_report = client.get_monthly_report()

client.close()

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
