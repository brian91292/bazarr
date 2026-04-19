# coding=utf-8

import logging
import importlib
import inspect
import os

from time import sleep
from datetime import datetime
from collections import deque
from typing import Any, Dict, List, Optional, Union
from threading import Event, Thread, Lock, RLock

from app.event_handler import event_stream
from app.config import settings

bazarr_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


class JobCancelled(Exception):
    """
    Raised cooperatively by a running job when it detects that its cancellation
    event has been set. ``JobsQueue._run_job`` catches this separately from
    generic ``Exception`` so that cancelled jobs are recorded with ``status='cancelled'``
    instead of ``status='failed'``.
    """
    pass


# Fields on ``Job`` that are internal and must never be serialized into API / websocket payloads.
# ``cancel_event`` in particular is a ``threading.Event`` which is not JSON-serializable.
_JOB_INTERNAL_FIELDS = frozenset({"cancel_event"})


def _job_to_dict(job: "Job") -> Dict[str, Any]:
    """
    Return a serializable view of a ``Job`` with internal-only fields stripped.

    Callers historically used ``vars(job)`` directly; switching to this helper
    ensures non-serializable attributes (e.g., ``threading.Event``) don't leak into
    API responses or event payloads.
    """
    return {k: v for k, v in vars(job).items() if k not in _JOB_INTERNAL_FIELDS}


class Job:
    """
    Represents a job with details necessary for its identification and execution.

    This class encapsulates information about a job, including its unique identifier,
    name, and the module or function it executes. It can also include optional
    arguments and keyword arguments for job execution. The status of the job is also
    tracked.

    :ivar job_id: Unique identifier of the job.
    :type job_id: int
    :ivar job_name: Descriptive name of the job.
    :type job_name: str
    :ivar module: Name of the module where the job function resides.
    :type module: str
    :ivar func: The name of the function to execute the job.
    :type func: str
    :ivar args: Positional arguments for the function, it defaults to None.
    :type args: list, optional
    :ivar kwargs: Keyword arguments for the function, it defaults to None.
    :type kwargs: dict, optional
    :ivar status: Current status of the job, initialized to 'pending'.
    :type status: str
    :ivar last_run_time: Last time the job was run, initialized to None.
    :type last_run_time: datetime
    :ivar is_progress: Indicates whether the job is a progress job, defaults to False.
    :type is_progress: bool
    :ivar is_signalr: Indicates whether the job as been initiated by a SignalR event, defaults to False.
    :type is_signalr: bool
    :ivar progress_value: Actual value of the job's progress, initialized to 0.
    :type progress_value: int
    :ivar progress_max: Maximum value of the job's progress, initialized to 0.
    :type progress_max: int
    :ivar progress_message: Message shown for this job's progress, initialized to an empty string.
    :type progress_message: str
    :ivar job_returned_value: Value returned by the job function, initialized to None.
    :type job_returned_value: Any
    """
    def __init__(self, job_id: int, job_name: str, module: str, func: str, args: list = None, kwargs: dict = None,
                 is_progress: bool = False, is_signalr: bool = False, progress_max: int = 0, job_returned_value=None,):
        self.job_id = job_id
        self.job_name = job_name
        self.module = module
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.status = 'pending'
        self.last_run_time = datetime.now()
        self.is_progress = is_progress
        self.is_signalr = is_signalr
        self.progress_value = 0
        self.progress_max = progress_max
        self.progress_message = ""
        self.job_returned_value = job_returned_value
        # Cooperative cancellation signal. Long-running job code should periodically
        # check ``is_set()`` (or call ``JobsQueue.is_cancelled(job_id)``) and raise
        # ``JobCancelled`` when set. Excluded from serialization via ``_JOB_INTERNAL_FIELDS``.
        self.cancel_event: Event = Event()

    def __eq__(self, other):
        """
        Custom equality check for job objects to compare only based on job_id when trying to remove existing jobs from
        queues.
        """
        return self.job_id == other.job_id


class JobsQueue:
    """
    Manages a queue of jobs, tracks their states, and processes them.

    This class is designed to handle a queue of jobs, enabling submission, tracking,
    and execution of tasks. Jobs are categorized into different queues (`pending`,
    `running`, `failed`, and `completed`) based on their current status. It provides
    methods to add, list, remove, and consume jobs in a controlled manner.

    :ivar jobs_pending_queue: Queue containing jobs that are pending execution.
    :type jobs_pending_queue: deque
    :ivar jobs_running_queue: Queue containing jobs that are currently being executed.
    :type jobs_running_queue: deque
    :ivar jobs_failed_queue: Queue containing jobs that failed during execution. It maintains a
        maximum size of 10 entries.
    :type jobs_failed_queue: deque
    :ivar jobs_completed_queue: Queue containing jobs that were executed successfully. It maintains
        a maximum size of 10 entries.
    :type jobs_completed_queue: deque
    :ivar current_job_id: Identifier of the latest job, incremented with each new job added to the queue.
    :type current_job_id: int
    """
    # Valid terminal / queryable queue names. Centralized so that adding a new
    # queue (e.g., ``cancelled``) doesn't require touching every touchpoint that
    # validates a queue-name argument.
    _QUEUE_NAMES: tuple = ('pending', 'running', 'failed', 'completed', 'cancelled')
    _CLEARABLE_QUEUES: tuple = ('pending', 'failed', 'completed', 'cancelled')

    def __init__(self):
        self.jobs_pending_queue: "deque[Job]" = deque()
        self.jobs_running_queue: "deque[Job]" = deque()
        self.jobs_failed_queue: "deque[Job]" = deque(maxlen=10)
        self.jobs_completed_queue: "deque[Job]" = deque(maxlen=10)
        # Jobs that were cancelled (either from pending or mid-run) land here so
        # that the UI can distinguish them from failed jobs.
        self.jobs_cancelled_queue: "deque[Job]" = deque(maxlen=10)
        self.current_job_id = 0

        # Add locks for thread safety
        self._queue_lock = RLock()  # Reentrant lock for nested operations
        self._job_id_lock = Lock()  # Separate lock for ID generation
        self._import_lock = Lock()  # Lock for module imports

    def feed_jobs_pending_queue(self, job_name, module, func, args: list = None, kwargs: dict = None,
                                is_progress=False, is_signalr=False, progress_max: int = 0,):
        """
        Adds a new job to the pending jobs queue with specified details and triggers an event
        to notify about the queue update. Each job is uniquely identified by a job ID,
        which is automatically incremented for each new job. Logging is performed to
        record the job addition.

        :param job_name: Name of the job to be added to the queue.
        :type job_name: str
        :param module: Module under which the job's function resides (ex: sonarr.sync.series).
        :type module: str
        :param func: Function name that represents the job (ex: update_series).
        :type func: str
        :param args: List of positional arguments to be passed to the function.
        :type args: list
        :param kwargs: Dictionary of keyword arguments to be passed to the function.
        :type kwargs: dict
        :param is_progress: Indicates whether the job is a progress job, defaults to False.
        :type is_progress: bool
        :param is_signalr: Indicates whether the job as been initiated by a SignalR event, defaults to False.
        :type is_signalr: bool
        :param progress_max: Maximum value of the job's progress, initialized to 0.
        :type progress_max: int
        :return: The unique job ID assigned to the newly queued job.
        :rtype: int
        """
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}

        with self._job_id_lock:
            new_job_id = self.current_job_id = self.current_job_id + 1
        
        with self._queue_lock:
            self.jobs_pending_queue.append(
                Job(job_id=new_job_id,
                    job_name=job_name,
                    module=module,
                    func=func,
                    args=args,
                    kwargs=kwargs,
                    is_progress=is_progress,
                    is_signalr=is_signalr,
                    progress_max=progress_max,)
            )
        
        logging.debug(f"Task {job_name} ({new_job_id}) added to queue")
        event_stream(type='jobs', action='update', payload={"job_id": new_job_id, "progress_value": None,
                                                            "status": "pending"})
        return new_job_id

    def list_jobs_from_queue(self, job_id: Optional[int] = None,
                             status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List jobs from a specific queue or all queues based on filters.

        This method retrieves job details from various job queues based on provided
        criteria. It can filter jobs by their `job_id` and/or their `status`. If no
        `job_id` or `status` is provided, it returns details of all jobs across
        all queues.

        :param job_id: Optional; The unique ID of the job to filter the results.
        :type job_id: int
        :param status: Optional; The status of jobs to filter the results. Expected
            values are 'pending', 'running', 'failed', 'completed', or 'cancelled'.
        :type status: str
        :return: A list of dictionaries with job details that match the given filters.
            If no matches are found, an empty list is returned.
        :rtype: list[dict]
        """
        if status:
            if status not in self._QUEUE_NAMES:
                return []
            # Direct attribute access — avoids the previous __dict__ lookup which
            # was fragile (any added attribute could shadow a queue lookup).
            queues = getattr(self, f'jobs_{status}_queue')
        else:
            queues = (self.jobs_pending_queue + self.jobs_running_queue
                      + self.jobs_failed_queue + self.jobs_completed_queue
                      + self.jobs_cancelled_queue)

        if job_id:
            return [_job_to_dict(job) for job in queues if job.job_id == job_id]
        return [_job_to_dict(job) for job in queues]

    def _find_job_in_queue(self, job_id: int, queue: "deque[Job]") -> Optional["Job"]:
        """
        Look up a ``Job`` instance by id inside a specific deque. Returns ``None``
        if no match is found. Extracted so that cancellation and other lookups
        don't have to duplicate the scan pattern.
        """
        for job in queue:
            if job.job_id == job_id:
                return job
        return None

    def get_job_status(self, job_id: int):
        """
        Retrieves the status of a job by its ID from a queue. If the job exists and has a
        status field, it returns its value. Otherwise, it returns "Unknown job".

        :param job_id: ID of the job to retrieve status for
        :type job_id: int
        :return: The status of the job if available, otherwise "Unknown job"
        :rtype: str
        """
        job = self.list_jobs_from_queue(job_id=job_id)
        if job and 'status' in job[0]:
            return job[0]['status']
        else:
            return "Unknown job"

    def update_job_name(self, job_id: int, new_job_name: str) -> bool:
        """
        Updates the name of a job present in one of the job queues. The job is searched by its unique
        identifier (`job_id`) in all available queues, and if found, the job's name is updated to
        `new_job_name`. After updating, it triggers an event to notify the frontend about the job update.

        :param job_id: The unique identifier of the job to be updated.
        :param new_job_name: The new name to assign to the job.
        :return: A boolean indicating whether the job name was successfully updated (True) or the job
                 was not found in any of the queues (False).
        """
        queues = self.jobs_pending_queue + self.jobs_running_queue + self.jobs_failed_queue + self.jobs_completed_queue
        
        for job in queues:
            if job.job_id == job_id:
                job.job_name = new_job_name
                event_stream(type='jobs', action='update', payload={"job_id": job.job_id})
                return True
        return False

    def get_job_returned_value(self, job_id: int):
        """
        Fetches the returned value of a job from the queue provided its unique identifier.

        This function retrieves the job details from the queue using the provided job
        identifier. If the job exists and contains a 'job_returned_value' key, the
        function returns the corresponding value. Otherwise, it defaults to returning
        None.

        :param job_id: The unique identifier of the job to fetch the returned value for.
        :type job_id: int
        :return: The returned value of the job if it exists, otherwise None.
        :rtype: Any
        """
        job = self.list_jobs_from_queue(job_id=job_id)
        if job and 'job_returned_value' in job[0]:
            return job[0]['job_returned_value']
        else:
            return None

    def update_job_progress(self, job_id: int, progress_value: Union[int, str, None] = None,
                            progress_max: Union[int, None] = None, progress_message: str = ""):
        """
        Updates the progress value and message for a specific job within the running jobs queue. The function
        iterates through a queue of running jobs, identifies the matching job by its ID, and updates its progress
        value and message. Afterward, triggers an event stream for the updated job.

        :param job_id: The unique identifier of the job to be updated.
        :type job_id: int
        :param progress_value: The new progress value to be set for the job. If 'max' is provided, progress_value will
        equal progress_max.
        :type progress_value: int or str or None
        :param progress_max: Maximum value of the job's progress.
        :type progress_max: int or None
        :param progress_message: An optional message providing additional details about the current progress.
        :type progress_message: str
        :return: Returns True if the job's progress was successfully updated, otherwise False.
        :rtype: bool
        """
        for job in self.jobs_running_queue:
            if job.job_id == job_id:
                payload = self._build_progress_payload(job, progress_value, progress_max, progress_message)
                event_stream(type='jobs', action='update', payload=payload)
                return True
        return False

    @staticmethod
    def _build_progress_payload(job, progress_value: Union[int, str, None],
                                progress_max: Union[int, None], progress_message: str):
        """
        Builds the payload dictionary for job progress updates and updates job attributes.

        :param job: The job instance to update.
        :param progress_value: The new progress value to be set for the job.
        :type progress_value: int or str or None
        :param progress_max: Maximum value of the job's progress.
        :type progress_max: int or None
        :param progress_message: An optional message providing additional details about the current progress.
        :type progress_message: str
        :return: Dictionary containing the payload for the event stream.
        :rtype: dict
        """
        payload = {"job_id": job.job_id, "status": job.status}
        progress_max_updated = False

        if progress_value:
            if progress_value == 'max':
                progress_value = job.progress_max or 1
                job.progress_value = job.progress_max = progress_value
                progress_max_updated = True
            else:
                job.progress_value = progress_value
        payload["progress_value"] = job.progress_value

        if progress_max and not progress_max_updated:
            job.progress_max = progress_max
        payload["progress_max"] = job.progress_max

        if progress_message:
            job.progress_message = progress_message
        payload["progress_message"] = job.progress_message

        return payload

    def update_job_progress_status(self, job_id: int, is_progress: bool = False) -> bool:
        """
        Updates the is_progress attribute for a specific job.

        :param job_id: The unique identifier of the job to be updated.
        :type job_id: int
        :param is_progress: The new value for is_progress attribute.
        :type is_progress: bool
        :return: Returns True if the job's progress status was successfully updated, otherwise False.
        :rtype: bool
        """
        for job in self.jobs_running_queue:
            if job.job_id == job_id:
                job.is_progress = is_progress
                event_stream(type='jobs', action='update', payload={"job_id": job.job_id})
                return True
        return False

    def add_job_from_function(self, job_name: str, is_progress: bool, progress_max: int = 0) -> int:
        """
        Adds a job to the pending queue using the details of the calling function. The job is then executed.

        :param job_name: Name of the job to be added.
        :type job_name: str
        :param is_progress: Flag indicating whether the progress of the job should be tracked.
        :type is_progress: bool
        :param progress_max: Maximum progress value for the job, default is 0.
        :type progress_max: int
        :return: ID of the added job.
        :rtype: int
        """
        # Get the current frame
        current_frame = inspect.currentframe()

        # Get the frame of the caller (parent function)
        # The caller's frame is at index 1 in the stack
        caller_frame = current_frame.f_back

        # Get the code object of the caller
        caller_code = caller_frame.f_code

        # Get the name of the parent function
        parent_function_name = caller_code.co_name

        # Get the file path of the parent function
        relative_parent_function_path = os.path.relpath(caller_code.co_filename, start=bazarr_dir)
        parent_function_path = os.path.splitext(relative_parent_function_path)[0].replace(os.sep, '.')

        # Get the function signature of the caller
        caller_signature = inspect.signature(inspect.getmodule(caller_code).__dict__[caller_code.co_name])
        # Get the local variables within the caller's frame
        caller_locals = caller_frame.f_locals

        bound_arguments = caller_signature.bind(**caller_locals)
        arguments = bound_arguments.arguments

        # Clean up the frame objects to prevent reference cycles
        del current_frame, caller_frame, caller_code, caller_signature, caller_locals, bound_arguments

        # Feed the job to the pending queue
        job_id = self.feed_jobs_pending_queue(job_name=job_name, module=parent_function_path, func=parent_function_name,
                                              kwargs=arguments, is_progress=is_progress, progress_max=progress_max)

        return job_id

    def remove_job_from_pending_queue(self, job_id: int):
        """
        Removes a job from the pending queue based on the provided job ID.

        This method iterates over the jobs in the pending queue and identifies the
        job that matches the given job ID. If the job exists in the queue, it is
        removed, and a debug message is logged. Additionally, an event is streamed
        to indicate the deletion action. If the job is not found, the method returns
        False.

        :param job_id: The ID of the job to be removed.
        :type job_id: int
        :return: A boolean indicating whether the removal was successful. Returns
                 True if the job was removed, otherwise False.
        :rtype: bool
        """
        for job in self.jobs_pending_queue:
            if job.job_id == job_id and job.status == 'pending':
                try:
                    self.jobs_pending_queue.remove(job)
                except ValueError:
                    return False
                else:
                    logging.debug(f"Task {job.job_name} ({job.job_id}) removed from queue")
                    event_stream(type='jobs', action='delete', payload={"job_id": job.job_id})
                    return True
        return False

    def move_job_in_pending_queue(self, job_id: int, move_destination: str) -> bool:
        """
        Moves a job within the pending queue to a specified location.

        This method attempts to move a job in the pending queue to either the
        top or bottom of the queue. It identifies the job by its ID and ensures
        that its status is 'pending' before performing the operation.

        :param job_id: The unique identifier of the job to move.
        :type job_id: int
        :param move_destination: Specifies where to move the job in the pending
            queue. Accepted values are 'top' and 'bottom'.
        :type move_destination: str
        :return: A boolean indicating whether the operation was successful.
        :rtype: bool
        """
        for job in self.jobs_pending_queue:
            if job.job_id == job_id and job.status == 'pending':
                try:
                    self.jobs_pending_queue.remove(job)
                except ValueError:
                    return False
                except Exception as e:
                    logging.exception(f"Unhandled exception while trying to move job {job.job_name} ({job.job_id}) in "
                                      f"pending queue: {e}")
                    return False
                else:
                    if move_destination == 'top':
                        self.jobs_pending_queue.appendleft(job)
                    elif move_destination == 'bottom':
                        self.jobs_pending_queue.append(job)
                    else:
                        logging.error(f"Invalid move destination: {move_destination}. Accepted values are 'top' and "
                                      f"'bottom'")
                        return False
                    logging.debug(f"Task {job.job_name} ({job.job_id}) moved to {move_destination} of the pending "
                                  f"queue")
                    event_stream(type='jobs', action='update', payload={"job_id": job.job_id})
                    return True
        return False

    def force_start_pending_job(self, job_id: int) -> bool:
        """
        Forces the execution of a job currently in the pending queue. Only jobs with
        a status of 'pending' will be processed. If a matching job is found and
        successfully initiated, the function returns True. Otherwise, it returns False.

        :param job_id: Identifier of the job to be forcefully started.
        :type job_id: int
        :return: A boolean value indicating whether the job was successfully initiated.
        :rtype: bool
        """
        for job in self.jobs_pending_queue:
            if job.job_id == job_id and job.status == 'pending':
                self._run_job(job_instance=job)
                return True
        return False

    def empty_jobs_queue(self, queue_name: str) -> bool:
        """
        Empties the jobs queue for a specified queue name if it exists among the predefined
        clearable queue categories. Clears all elements within the specified queue and indicates
        success or failure for the operation. The ``running`` queue is intentionally excluded
        — clearing a running queue would orphan in-flight work; use :meth:`cancel` instead.

        :param queue_name: The name of the queue to be emptied. Must be one of
            ``'pending'``, ``'failed'``, ``'completed'``, ``'cancelled'``.
        :type queue_name: str

        :return: A boolean value indicating whether the specified queue was successfully emptied.
        :rtype: bool
        """
        if queue_name in self._CLEARABLE_QUEUES:
            logging.debug(f"Emptying jobs queue for {queue_name} jobs")
            with self._queue_lock:
                getattr(self, f'jobs_{queue_name}_queue').clear()
            return True
        return False

    def is_cancelled(self, job_id: Optional[int]) -> bool:
        """
        Report whether the job with ``job_id`` has been flagged for cancellation.

        Intended for hot loops inside long-running jobs — cheaper than constructing
        a full job dict and safe to call at high frequency. Returns ``False`` if
        ``job_id`` is ``None`` or the job isn't found (e.g., already moved to a
        terminal queue), so callers can poll without guarding for missing ids.

        :param job_id: The id of the running job (usually the ``job_id`` kwarg
            injected by :meth:`_run_job`).
        :return: ``True`` when the job's ``cancel_event`` is set; ``False`` otherwise.
        """
        if job_id is None:
            return False
        with self._queue_lock:
            job = (self._find_job_in_queue(job_id, self.jobs_running_queue)
                   or self._find_job_in_queue(job_id, self.jobs_pending_queue))
        if job is None:
            return False
        return job.cancel_event.is_set()

    def check_cancelled(self, job_id: Optional[int]) -> None:
        """
        Raise :class:`JobCancelled` if the given job has been flagged for cancellation.

        Convenience wrapper around :meth:`is_cancelled` for the common pattern of
        ``check-and-raise`` at the top of a loop iteration.
        """
        if self.is_cancelled(job_id):
            raise JobCancelled(f"Job {job_id} was cancelled")

    def cancel(self, job_id: int) -> bool:
        """
        Cancel a job regardless of whether it's pending or running.

        Behavior by current state:
            * **pending**  – removed from the pending queue, recorded in the cancelled queue.
            * **running**  – its ``cancel_event`` is set. The job's own code must
              periodically check the event (via :meth:`is_cancelled` /
              :meth:`check_cancelled`) and raise :class:`JobCancelled` to stop
              promptly; :meth:`_run_job` will then move it into the cancelled queue.
            * any other state – nothing to do; returns ``False``.

        A ``jobs`` event is emitted on the event stream for UI updates.

        :param job_id: Id of the job to cancel.
        :return: ``True`` if a cancel signal was issued (pending removed or running
            flagged), ``False`` if no such active job exists.
        """
        with self._queue_lock:
            # 1. Pending path: we can synchronously short-circuit execution.
            pending_job = self._find_job_in_queue(job_id, self.jobs_pending_queue)
            if pending_job is not None and pending_job.status == 'pending':
                try:
                    self.jobs_pending_queue.remove(pending_job)
                except ValueError:
                    # Raced with the consumer thread picking it up; fall through
                    # to the running-queue handling below.
                    pending_job = None
                else:
                    pending_job.status = 'cancelled'
                    pending_job.last_run_time = datetime.now()
                    pending_job.cancel_event.set()
                    self.jobs_cancelled_queue.append(pending_job)
                    logging.info(f"Task {pending_job.job_name} ({pending_job.job_id}) "
                                 f"cancelled before execution")
                    event_stream(type='jobs', action='update',
                                 payload={"job_id": pending_job.job_id,
                                          "status": "cancelled",
                                          "progress_value": None})
                    return True

            # 2. Running path: flag the event and let the job's cooperative checks stop it.
            running_job = self._find_job_in_queue(job_id, self.jobs_running_queue)
            if running_job is not None:
                if running_job.cancel_event.is_set():
                    # Already requested — idempotent no-op, but still report success
                    # so the caller UI stays consistent.
                    return True
                running_job.cancel_event.set()
                logging.info(f"Task {running_job.job_name} ({running_job.job_id}) "
                             f"cancellation requested while running")
                event_stream(type='jobs', action='update',
                             payload={"job_id": running_job.job_id,
                                      "status": "cancelling",
                                      "progress_message": "Cancelling…"})
                return True

        return False

    def consume_jobs_pending_queue(self):
        """
        Continuously consumes jobs from the pending jobs queue and processes them by starting a new thread
        for each job, subject to the limit of concurrent jobs allowed in the running queue.

        The function will terminate in response to a KeyboardInterrupt or SystemExit exception.

        :raises KeyboardInterrupt: If the execution is interrupted manually.
        :raises SystemExit: If the execution is interrupted by a system exit event.
        """
        while True:
            try:
                if self.jobs_pending_queue:
                    with self._queue_lock:
                        can_run_job = (len(self.jobs_running_queue) < settings.general.concurrent_jobs
                                       and len(self.jobs_pending_queue) > 0)

                    if can_run_job:
                        job_thread = Thread(target=self._run_job)
                        job_thread.daemon = True
                        job_thread.start()
                    else:
                        sleep(0.5)
                else:
                    sleep(0.5)
            except (KeyboardInterrupt, SystemExit):
                break

    def _run_job(self, job_instance=None) -> bool:
        """
        Handles the execution of a job from the pending jobs queue or an explicitly provided
        job instance. Manages job state transitions including updating job status, generating
        event streams for job status updates, and handling job results or exceptions.

        :param job_instance: Optional; Specific job instance to execute. If not provided,
            a job will be dequeued from the pending jobs queue.
        :type job_instance: Optional[Job]
        :return: A boolean indicating the success or failure of the job execution. Returns
            True if the job was successfully completed, otherwise False.
        :rtype: bool
        """
        # Hold the queue lock across pending-removal AND running-append so that
        # concurrent cancel() calls always see the job in exactly one of the two
        # queues — no race window where the job is invisible to cancellation.
        with self._queue_lock:
            if job_instance:
                job = job_instance
                try:
                    self.jobs_pending_queue.remove(job)
                except ValueError:
                    # Already removed (e.g., by cancel()); don't double-run.
                    return False
            else:
                if not self.jobs_pending_queue:
                    return False
                job = self.jobs_pending_queue.popleft()

            if not job:
                sleep(0.1)
                return False

            job.status = 'running'
            job.last_run_time = datetime.now()
            if 'job_id' not in job.kwargs or not job.kwargs['job_id']:
                job.kwargs['job_id'] = job.job_id
            self.jobs_running_queue.append(job)

        try:
            # Guard against the rare race where cancel() set the event between
            # feed_jobs_pending_queue and _run_job dequeueing it. This catches
            # cancellations issued against the pending job before execution starts.
            if job.cancel_event.is_set():
                raise JobCancelled(f"Job {job.job_id} cancelled before start")

            # sending event to update the status of progress jobs
            payload = {"job_id": job.job_id, "status": job.status}
            if job.is_progress:
                payload["progress_value"] = None
                payload["progress_max"] = job.progress_max
                payload["progress_message"] = job.progress_message
            event_stream(type='jobs', action='update', payload=payload)

            logging.debug(f"Running job {job.job_name} (id {job.job_id}): "
                          f"{job.module}.{job.func}({job.args}, {job.kwargs})")

            # Use import lock to prevent deadlocks
            with self._import_lock:
                module = importlib.import_module(job.module)

            job.job_returned_value = getattr(module, job.func)(*job.args, **job.kwargs)
        except JobCancelled:
            # Cooperative cancellation — distinct terminal state from 'failed'.
            logging.info(f"Job {job.job_name} ({job.job_id}) cancelled")
            job.status = 'cancelled'
            job.last_run_time = datetime.now()
            # Remove from running queue if present (it may not be if we raised
            # before appending, though that path isn't currently reachable).
            try:
                self.jobs_running_queue.remove(job)
            except ValueError:
                pass
            self.jobs_cancelled_queue.append(job)
            return False
        except Exception as e:
            logging.exception(f"Exception raised while running function: {e}")
            job.status = 'failed'
            job.last_run_time = datetime.now()
            try:
                self.jobs_running_queue.remove(job)
            except ValueError:
                pass
            self.jobs_failed_queue.append(job)
            return False
        else:
            job.status = 'completed'
            job.last_run_time = datetime.now()
            try:
                self.jobs_running_queue.remove(job)
            except ValueError:
                pass
            self.jobs_completed_queue.append(job)
            return True
        finally:
            try:
                # Send a complete event payload with status and progress_value
                # progress_value being None forces frontend to fetch a full job payload
                payload = {
                    "job_id": job.job_id,
                    "status": job.status,  # 'completed', 'failed', or 'cancelled'
                    "progress_value": None  # Trigger frontend API call to update the whole job payload
                }
                event_stream(type='jobs', action='update', payload=payload)
            except Exception as e:
                logging.exception(f"Exception raised while sending event: {e}")


jobs_queue = JobsQueue()
